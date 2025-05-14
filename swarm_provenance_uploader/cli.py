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
    stamp_check_retries: Annotated[int, typer.Option("--stamp-retries", help="Number of times to check for stamp usability.")] = 12, # Increased default retries
    stamp_check_interval: Annotated[int, typer.Option("--stamp-interval", help="Seconds to wait between stamp usability checks.")] = 20 # Increased default interval
 ):
    """
    Hashes, Base64-encodes, wraps, and Uploads a
    provenance data file to Swarm.
    """
    typer.echo(f"--> Processing file: {file}")
    typer.echo(f"    Gateway URL: {gateway_url}")
    typer.echo(f"    Stamp Depth: {stamp_depth}")
    typer.echo(f"    Stamp Amount: {stamp_amount}")

    # 1. Read raw provenance file content
    try:
        raw_content = file_utils.read_file_content(file)
    except Exception as e:
        typer.secho(f"ERROR: Failed reading file: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # 2. SHA256 hash raw content
    sha256_hash = file_utils.calculate_sha256(raw_content)
    typer.echo(f"    SHA256 Hash: {sha256_hash}")

    # 3. Base64 encode raw content
    b64_encoded_data = file_utils.base64_encode_data(raw_content)

    # 4. Determine Payload Size for Stamp Purchase
    # Build a temporary metadata object with a placeholder stamp to calculate size
    try:
       temp_metadata_for_size_calc = metadata_builder.create_provenance_metadata_object(
            base64_data=b64_encoded_data,
            content_hash=sha256_hash,
            stamp_id="0"*64, # Placeholder, 64 hex chars
            provenance_standard=provenance_standard,
            encryption=encryption
        )
       payload_to_upload_bytes = metadata_builder.serialize_metadata_to_bytes(temp_metadata_for_size_calc)
       payload_size = file_utils.get_data_size(payload_to_upload_bytes)
       typer.echo(f"    Estimated Metadata Payload Size: {payload_size} bytes")
    except Exception as e:
       typer.secho(f"ERROR: Failed preparing metadata structure: {e}", fg=typer.colors.RED, err=True)
       raise typer.Exit(code=1)



    # 5 & 6. Request postage stamp
    typer.echo(f"--> Purchasing postage stamp from {gateway_url}...")
    typer.echo(f"    Using Amount: {stamp_amount}, Depth: {stamp_depth}")
    stamp_id = None
    try:
        stamp_id = swarm_client.purchase_postage_stamp(gateway_url, stamp_amount, stamp_depth)
        typer.echo(f"    Stamp ID Received: {stamp_id} (Length: {len(stamp_id)})")
        typer.echo(f"    Ensuring stamp_id is lowercase for checks: {stamp_id.lower()}")
    except Exception as e:
        typer.secho(f"ERROR: Failed purchasing stamp: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # Poll for stamp existence and usability
    typer.echo(f"--> Checking for stamp usability (ID: {stamp_id.lower()}). Max Retries: {stamp_check_retries}, Interval: {stamp_check_interval}s")
    stamp_is_ready_for_upload = False # Changed variable name for clarity
    for i in range(stamp_check_retries):
        typer.echo(f"    Attempt {i+1}/{stamp_check_retries} to check stamp...")
        try:
            stamp_info = swarm_client.get_stamp_info(gateway_url, stamp_id)
            if stamp_info:
                # Print the full stamp_info for better debugging if needed
                # typer.echo(f"    Raw Stamp Info: {stamp_info}")
                
                exists = stamp_info.get("exists", False) # Default to False if 'exists' key is missing
                usable = stamp_info.get("usable", False) # Default to False if 'usable' key is missing
                batch_ttl = stamp_info.get("batchTTL", "N/A")

                typer.echo(f"    Stamp found: Exists={exists}, Usable={usable}, TTL={batch_ttl}s")

                if exists and usable:
                    stamp_is_ready_for_upload = True
                    typer.secho(f"    Stamp {stamp_id.lower()} is now USABLE!", fg=typer.colors.GREEN)
                    break
                else:
                    typer.echo(f"    Stamp {stamp_id.lower()} not yet usable (Exists: {exists}, Usable: {usable}). Retrying...")
            else: # stamp_info was None, meaning a 404 or other issue handled by get_stamp_info
                typer.echo(f"    Stamp {stamp_id.lower()} not found or error during check. Retrying...")

        except Exception as e: # Catch errors from get_stamp_info itself
            typer.echo(f"    Warning: Error during stamp info check on attempt {i+1}: {e}")
            # Continue to next retry

        if i < stamp_check_retries - 1: # Don't sleep after the last attempt
            typer.echo(f"    Waiting {stamp_check_interval}s before next check...")
            time.sleep(stamp_check_interval)

    if not stamp_is_ready_for_upload:
        typer.secho(f"ERROR: Stamp {stamp_id.lower()} did not become USABLE after {stamp_check_retries} retries.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # 7. (Final) Construct "Provenance Metadata" JSON object using real stamp_id
    final_metadata_obj = metadata_builder.create_provenance_metadata_object(
            base64_data=b64_encoded_data,
            content_hash=sha256_hash,
            stamp_id=stamp_id, # Use the REAL stamp ID
            provenance_standard=provenance_standard,
            encryption=encryption
     )
    final_payload_bytes = metadata_builder.serialize_metadata_to_bytes(final_metadata_obj)

    # 8 & 9. Upload "Provenance Metadata" JSON
    typer.echo(f"--> Uploading metadata to Swarm using stamp {stamp_id}...")
    try:
        swarm_ref_hash = swarm_client.upload_data(gateway_url, final_payload_bytes, stamp_id)
    except Exception as e:
        typer.secho(f"ERROR: Failed uploading data: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # 10. Display Swarm reference_hash
    typer.secho(f"\nSUCCESS! Upload complete.", fg=typer.colors.GREEN, bold=True)
    typer.echo("\nSwarm Reference Hash:")
    typer.secho(f"{swarm_ref_hash}", fg=typer.colors.CYAN)


@app.callback()
def main():
     """
     Swarm Provenance CLI Toolkit
     """
     pass

# Required for script execution
if __name__ == "__main__":
     app()
