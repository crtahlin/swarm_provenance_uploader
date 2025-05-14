from pydantic import BaseModel, Field
from typing import Optional

class ProvenanceMetadata(BaseModel):
    """
     Defines the structure for the metadata JSON that wraps
     the base64-encoded provenance data.
    """
    data: str = Field(description="Base64 encoded string of the original provenance file content.")
    content_hash: str = Field(description="SHA256 hash of the original, raw provenance file content.")
    stamp_id: str = Field(description="Swarm Postage Stamp ID used for this upload.")
    provenance_standard: Optional[str] = Field(default=None, description="Identifier for the provenance standard used (e.g., 'PROV-O').")
    encryption: Optional[str] = Field(default=None, description="Details about encryption scheme, if any, used on ORIGINAL data.")

    # Ensure Pydantic V2 compatibility if needed elsewhere
    # model_config = {
    #     "json_schema_extra": {
    #         "examples": [
    #             {
    #                 "data": "dGVzdCBkYXRh",
    #                 "content_hash": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08", # hash of 'test data'
    #                 "stamp_id": "a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3a3",
    #                 "provenance_standard": "MY-STANDARD-V1",
    #                  "encryption": "None"
    #             }
    #         ]
    #     }
    # }
