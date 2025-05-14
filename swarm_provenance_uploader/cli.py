import typer
from typing import Optional
from typing_extensions import Annotated
from pathlib import Path
import sys
import time
import json

from . import config
from .core import file_utils, swarm_client, metadata_builder
from .models import ProvenanceMetadata, ValidationError

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

@app.command()
def download(
    swarm_hash: Annotated[str, typer.Argument(help="Swarm reference hash of the Provenance Metadata to download.")],
    output_dir: Annotated[Path, typer.Option(
        "--output-dir", "-o",
        help="Directory to save the downloaded files.",
        file_okay=False,
        dir_okay=True,
        writable=True,
        resolve_path=True,
        default_factory=lambda: Path.cwd() # Default to current working directory
    )],
    gateway_url: Annotated[str, typer.Option(help=f"Bee Gateway URL. [default: {config.BEE_GATEWAY_URL}]" )] = config.BEE_GATEWAY_URL,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose output for debugging.")] = False
):
    """
    Downloads Provenance Metadata from Swarm, decodes the wrapped data,
    verifies its integrity, and saves both files.
    """
    if verbose:
        typer.echo("Verbose mode enabled.")
        typer.echo(f"--> Initial Config for Download:")
        typer.echo(f"    Swarm Hash: {swarm_hash}")
        typer.echo(f"    Output Directory: {output_dir}")
        typer.echo(f"    Gateway URL: {gateway_url}")
    else:
        typer.echo(f"Downloading data for Swarm hash: {swarm_hash[:12]}...")

    # 1 & 2. Request and retrieve data (Provenance Metadata JSON bytes)
    typer.echo(f"Fetching metadata from Swarm via {gateway_url}...")
    try:
        metadata_bytes = swarm_client.download_data_from_swarm(gateway_url, swarm_hash, verbose=verbose)
        if verbose:
            typer.echo(f"    Successfully fetched {len(metadata_bytes)} bytes of metadata.")
    except FileNotFoundError as e:
        typer.secho(f"ERROR: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(f"ERROR: Failed fetching metadata from Swarm: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # 3. Deserialize fetched data to "Provenance Metadata" JSON object
    try:
        metadata_str = metadata_bytes.decode('utf-8')
        # provenance_metadata_obj = ProvenanceMetadata(**json.loads(metadata_str)) # Old Pydantic v1 way
        provenance_metadata_obj = ProvenanceMetadata.model_validate_json(metadata_str) # Pydantic v2 way
        if verbose:
            typer.echo("    Successfully parsed metadata JSON.")
            # typer.echo(f"    Parsed Metadata: {provenance_metadata_obj.model_dump(exclude={'data'})}") # Exclude large data field
    except (json.JSONDecodeError, ValidationError) as e: # Catch Pydantic validation errors too
        typer.secho(f"ERROR: Fetched data is not valid Provenance Metadata JSON: {e}", fg=typer.colors.RED, err=True)
        # Optionally save the invalid data for inspection
        try:
            invalid_data_path = output_dir / f"{swarm_hash}.invalid_metadata.txt"
            file_utils.save_bytes_to_file(invalid_data_path, metadata_bytes)
            typer.echo(f"    Saved invalid data to: {invalid_data_path}")
        except Exception as save_e:
            typer.echo(f"    Could not save invalid data: {save_e}")
        raise typer.Exit(code=1)
    except Exception as e: # Catch other unexpected errors
        typer.secho(f"ERROR: Unexpected error parsing metadata: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)


    # 4. Validate expected JSON structure (Pydantic does this on parsing)
    #    and check for essential fields if not using Pydantic or for extra safety.
    #    Pydantic model already ensures 'data' and 'content_hash' exist if parsing succeeds.

    # 5. Extract Base64 encoded data
    b64_encoded_original_data = provenance_metadata_obj.data
    if verbose:
        typer.echo(f"    Extracted Base64 data (first 50 chars): {b64_encoded_original_data[:50]}...")

    # 6. Base64 decode
    try:
        raw_provenance_bytes = file_utils.base64_decode_data(b64_encoded_original_data)
        if verbose:
            typer.echo(f"    Successfully Base64 decoded {len(raw_provenance_bytes)} bytes of original data.")
    except ValueError as e:
        typer.secho(f"ERROR: Failed to Base64 decode data from metadata: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # 7. Calculate SHA256 hash of raw_provenance_bytes
    calculated_content_hash = file_utils.calculate_sha256(raw_provenance_bytes)
    if verbose:
        typer.echo(f"    Calculated SHA256 of decoded data: {calculated_content_hash}")

    # 8. Extract expected_hash
    expected_content_hash = provenance_metadata_obj.content_hash
    if verbose:
        typer.echo(f"    Expected SHA256 from metadata:    {expected_content_hash}")

    # Perform verification and save files
    output_dir.mkdir(parents=True, exist_ok=True) # Ensure output directory exists

    # 10. Save "Provenance Metadata" JSON
    metadata_filename = f"{swarm_hash}.meta.json"
    metadata_filepath = output_dir / metadata_filename
    try:
        # Save the pretty-printed JSON version of the Pydantic model
        file_utils.save_bytes_to_file(metadata_filepath, provenance_metadata_obj.model_dump_json(indent=2).encode('utf-8'))
        typer.echo(f"Provenance metadata saved to: {metadata_filepath}")
    except Exception as e:
        typer.secho(f"ERROR: Failed to save metadata file: {e}", fg=typer.colors.RED, err=True)
        # Continue to try and save data if verification passes, or decide to exit

    # 9. Verification
    if calculated_content_hash == expected_content_hash:
        typer.secho("SUCCESS: Content hash verification passed!", fg=typer.colors.GREEN)
        # 11. Save decoded raw_provenance_bytes
        data_filename = f"{swarm_hash}.data"
        data_filepath = output_dir / data_filename
        try:
            file_utils.save_bytes_to_file(data_filepath, raw_provenance_bytes)
            typer.echo(f"Decoded provenance data saved to: {data_filepath}")
            typer.secho(f"\nDownload and verification successful.", fg=typer.colors.GREEN, bold=True)
        except Exception as e:
            typer.secho(f"ERROR: Failed to save decoded data file: {e}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
    else:
        typer.secho("ERROR: Content hash verification FAILED!", fg=typer.colors.RED, bold=True)
        typer.echo(f"  Calculated hash: {calculated_content_hash}")
        typer.echo(f"  Expected hash:   {expected_content_hash}")
        # Optionally save the (unverified) decoded data with a warning filename
        unverified_data_filename = f"{swarm_hash}.UNVERIFIED.data"
        unverified_data_filepath = output_dir / unverified_data_filename
        try:
            file_utils.save_bytes_to_file(unverified_data_filepath, raw_provenance_bytes)
            typer.echo(f"Decoded (but UNVERIFIED) data saved to: {unverified_data_filepath}")
        except Exception as e:
            typer.echo(f"Could not save unverified data: {e}")
        raise typer.Exit(code=1)


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
