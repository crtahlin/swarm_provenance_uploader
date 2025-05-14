import typer
from typing import Optional
from typing_extensions import Annotated
from pathlib import Path
import sys
import time

from . import config
from .core import file_utils, swarm_client, metadata_builder

app = typer.Typer(help="Swarm Provenance CLI - Wraps and uploads data to Swarm.")

@app.command()
def upload(
    file: Annotated[Path, typer.Option(
        ...,
        "--file",
        "-f",
        help="Path to the provenance data file to wrap and upload.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        )
     ],
    provenance_standard: Annotated[Optional[str], typer.Option("--std", help="Identifier for the provenance standard used (optional).")] = None,
    encryption: Annotated[Optional[str], typer.Option("--enc", help="Details about encryption used (optional).")] = None,
    gateway_url: Annotated[str, typer.Option(help=f"Bee Gateway URL. [default: {config.BEE_GATEWAY_URL}]" )] = config.BEE_GATEWAY_URL,
    stamp_depth: Annotated[int, typer.Option(help=f"Postage stamp depth. [default: {config.DEFAULT_POSTAGE_DEPTH}]")] = config.DEFAULT_POSTAGE_DEPTH,
    stamp_amount: Annotated[int, typer.Option(help=f"Postage stamp amount. [default: {config.DEFAULT_POSTAGE_AMOUNT}]")] = config.DEFAULT_POSTAGE_AMOUNT,
    stamp_check_retries: Annotated[int, typer.Option("--stamp-retries", help="Number of times to check for stamp usability.")] = 12,
    stamp_check_interval: Annotated[int, typer.Option("--stamp-interval", help="Seconds to wait between stamp usability checks.")] = 20,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose output for debugging.")] = False # New verbose flag
 ):
    """
    Hashes, Base64-encodes, wraps, and Uploads a
    provenance data file to Swarm.
    """
    if verbose:
        typer.echo("Verbose mode enabled.")
        typer.echo(f"--> Initial Config:")
        typer.echo(f"    File: {file}")
        typer.echo(f"    Gateway URL: {gateway_url}")
        typer.echo(f"    Stamp Depth: {stamp_depth}")
        typer.echo(f"    Stamp Amount: {stamp_amount}")
        typer.echo(f"    Stamp Check Retries: {stamp_check_retries}")
        typer.echo(f"    Stamp Check Interval: {stamp_check_interval}s")
    else:
        typer.echo(f"Processing file: {file.name}...")


    # 1-4. Read file, hash, base64, estimate size
    try:
        raw_content = file_utils.read_file_content(file)
    except Exception as e:
        typer.secho(f"ERROR: Failed reading file '{file.name}': {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    sha256_hash = file_utils.calculate_sha256(raw_content)
    if verbose:
        typer.echo(f"    SHA256 Hash: {sha256_hash}")
    b64_encoded_data = file_utils.base64_encode_data(raw_content)

    try:
       temp_metadata_for_size_calc = metadata_builder.create_provenance_metadata_object(
            base64_data=b64_encoded_data, content_hash=sha256_hash, stamp_id="0"*64,
            provenance_standard=provenance_standard, encryption=encryption )
       payload_to_upload_bytes = metadata_builder.serialize_metadata_to_bytes(temp_metadata_for_size_calc)
       # payload_size = file_utils.get_data_size(payload_to_upload_bytes) # Not strictly needed for user output unless verbose
       # if verbose:
       #     typer.echo(f"    Estimated Metadata Payload Size: {payload_size} bytes")
    except Exception as e:
       typer.secho(f"ERROR: Failed preparing metadata structure: {e}", fg=typer.colors.RED, err=True)
       raise typer.Exit(code=1)

    # 5 & 6. Request postage stamp
    typer.echo(f"Purchasing postage stamp...")
    if verbose:
        typer.echo(f"    (Amount: {stamp_amount}, Depth: {stamp_depth} from {gateway_url})")
    stamp_id = None
    try:
        stamp_id = swarm_client.purchase_postage_stamp(gateway_url, stamp_amount, stamp_depth, verbose=verbose) # Pass verbose
        if verbose:
            typer.echo(f"    Stamp ID Received: {stamp_id} (Length: {len(stamp_id)})")
            typer.echo(f"    Stamp ID (lowercase for header): {stamp_id.lower()}")
        else:
            typer.echo(f"Postage stamp purchased (ID: ...{stamp_id[-12:]})")

    except Exception as e:
        typer.secho(f"ERROR: Failed purchasing stamp: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # Poll for stamp existence and usability
    typer.echo(f"Waiting for stamp to become usable (up to {stamp_check_retries * stamp_check_interval // 60} minutes)...")
    stamp_is_ready_for_upload = False
    for i in range(stamp_check_retries):
        if not verbose:
            # Simple progress indicator for non-verbose mode
            typer.echo(f"Checking stamp usability (attempt {i+1}/{stamp_check_retries})... ", nl=False)

        try:
            # Pass verbose to get_stamp_info as well
            stamp_info = swarm_client.get_stamp_info(gateway_url, stamp_id, verbose=verbose)
            if stamp_info:
                exists = stamp_info.get("exists", False)
                usable = stamp_info.get("usable", False)
                batch_ttl_seconds = stamp_info.get("batchTTL") # TTL in seconds

                if verbose:
                    ttl_str = f"{batch_ttl_seconds // 60}m {batch_ttl_seconds % 60}s" if batch_ttl_seconds is not None else "N/A"
                    typer.echo(f"    Attempt {i+1}: Stamp found - Exists={exists}, Usable={usable}, TTL={ttl_str}")

                if exists and usable:
                    stamp_is_ready_for_upload = True
                    if not verbose: typer.echo(typer.style("OK", fg=typer.colors.GREEN))
                    else: typer.secho(f"    Stamp {stamp_id.lower()} is now USABLE!", fg=typer.colors.GREEN)
                    break
                else:
                    if not verbose: typer.echo("retrying...") # Clearer than just "retrying..."
                    # else: typer.echo(f"    Stamp {stamp_id.lower()} not yet usable. Retrying...") # Already covered by verbose block
            else:
                if not verbose: typer.echo("not found, retrying...")
                # else: typer.echo(f"    Stamp {stamp_id.lower()} not found or error during check. Retrying...") # Already covered

        except Exception as e:
            if not verbose: typer.echo(typer.style("error checking, retrying...", fg=typer.colors.YELLOW))
            else: typer.echo(f"    Warning: Error during stamp info check on attempt {i+1}: {e}")


        if i < stamp_check_retries - 1:
            if verbose:
                typer.echo(f"    Waiting {stamp_check_interval}s before next check...")
            time.sleep(stamp_check_interval)
        elif not stamp_is_ready_for_upload and not verbose: # Last attempt failed, print newline
            typer.echo(typer.style("failed.", fg=typer.colors.RED))


    if not stamp_is_ready_for_upload:
        typer.secho(f"ERROR: Stamp {stamp_id.lower()} did not become USABLE after {stamp_check_retries} retries.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # 7. (Final) Construct "Provenance Metadata" JSON object
    final_metadata_obj = metadata_builder.create_provenance_metadata_object(
            base64_data=b64_encoded_data, content_hash=sha256_hash, stamp_id=stamp_id,
            provenance_standard=provenance_standard, encryption=encryption )
    final_payload_bytes = metadata_builder.serialize_metadata_to_bytes(final_metadata_obj)
    if verbose:
        typer.echo(f"    Final Metadata Object created with stamp_id: {final_metadata_obj.stamp_id}")
        typer.echo(f"    Preview of final_payload_bytes (first 100): {final_payload_bytes[:100].decode('utf-8', errors='replace')}...")

    # 8 & 9. Upload "Provenance Metadata" JSON
    typer.echo(f"Uploading data to Swarm...")
    if verbose:
        typer.echo(f"    (Using stamp_id: {stamp_id.lower()} in header)")
    try:
        swarm_ref_hash = swarm_client.upload_data(gateway_url, final_payload_bytes, stamp_id, verbose=verbose) # Pass verbose
    except Exception as e:
        typer.secho(f"ERROR: Failed uploading data: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # 10. Display Swarm reference_hash
    typer.secho(f"\nSUCCESS! Upload complete.", fg=typer.colors.GREEN, bold=True)
    typer.echo("Swarm Reference Hash:")
    typer.secho(f"{swarm_ref_hash}", fg=typer.colors.CYAN)


@app.callback()
def main(
    ctx: typer.Context, # Context object for Typer
    # Add global options here if needed later, e.g. for config file
):
     """
     Swarm Provenance CLI Toolkit - Wraps and uploads data to Swarm.
     Use --verbose for detailed debug output.
     """
     # You can use ctx.obj to pass objects between commands if you add subcommands
     pass

if __name__ == "__main__":
     app()
