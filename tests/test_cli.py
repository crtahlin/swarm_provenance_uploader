import pytest
from typer.testing import CliRunner
from swarm_provenance_uploader.cli import app # Assuming app is your Typer instance

# Create a Typer Test Runner
runner = CliRunner()

# Use pytest-mock 'mocker' fixture, or requests-mock
# This example uses mocker

DUMMY_HASH = "a028d9370473556397e189567c07279195890a16886002103369966898407152"
DUMMY_STAMP = "a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3"
DUMMY_SWARM_REF="b5d4ea763a1396676771151158461f73678f1676166acd06a0a18600b85de8a4"


def test_upload_command_success(mocker):
     """
    Tests the CLI upload command, mocking out the swarm client calls.
     """
     # Mock the functions in the swarm_client module
     m_purchase_stamp = mocker.patch(
         "swarm_provenance_uploader.core.swarm_client.purchase_postage_stamp",
         return_value=DUMMY_STAMP
      )
     m_upload_data = mocker.patch(
         "swarm_provenance_uploader.core.swarm_client.upload_data",
          return_value=DUMMY_SWARM_REF
      )

     # Use the runner to simulate running in a temporary, isolated filesystem
     with runner.isolated_filesystem():
         # Create a dummy file for the CLI to "read"
         TEST_FILENAME="my_data.txt"
         with open(TEST_FILENAME, "w") as f:
             f.write("some provenance data")

         # Invoke the CLI command
         result = runner.invoke(
              app,
              [
                  "upload",
                  "--file",
                   TEST_FILENAME,
                  "--std",
                   "TESTING-V1"
              ]
          )

        # Assertions
         assert result.exit_code == 0, f"CLI Failed: {result.stdout}"
         assert DUMMY_STAMP in result.stdout
         assert DUMMY_SWARM_REF in result.stdout
         assert "SUCCESS!" in result.stdout

         m_purchase_stamp.assert_called_once()
         m_upload_data.assert_called_once()
        
         # Check that the stamp_id passed to upload_data was the correct one
         args, kwargs = m_upload_data.call_args
         assert kwargs.get('stamp_id') == DUMMY_STAMP
        
def test_upload_command_file_not_found():
     """ Tests CLI exits correctly if file does not exist """
     result = runner.invoke(app, ["upload", "--file", "non_existent_file.dat"])
     assert result.exit_code != 0
     assert "Invalid value" in result.stdout # Typer's 'exists=True' handles this

def test_upload_stamp_purchase_fails(mocker):
     """ Tests CLI exits correctly if stamp purchase fails """

     m_purchase_stamp = mocker.patch(
         "swarm_provenance_uploader.core.swarm_client.purchase_postage_stamp",
         side_effect=ConnectionError("Mock Connection Error")
      )

     with runner.isolated_filesystem():
         with open("my_data.txt", "w") as f:
             f.write("some data")

         result = runner.invoke(app, ["upload", "--file", "my_data.txt"])

         assert result.exit_code == 1
         assert "ERROR: Failed purchasing stamp" in result.stdout
         m_purchase_stamp.assert_called_once()
