from typing import Optional
from swarm_provenance_uploader.models import ProvenanceMetadata

def create_provenance_metadata_object(
    base64_data: str,
    content_hash: str,
    stamp_id: str,
    provenance_standard: Optional[str] = None,
    encryption: Optional[str] = None
    ) -> ProvenanceMetadata:
        """
        Instantiates the ProvenanceMetadata Pydantic model.
        Returns the model instance.
        """
        metadata = ProvenanceMetadata(
             data=base64_data,
             content_hash=content_hash,
             stamp_id=stamp_id,
             provenance_standard=provenance_standard,
             encryption=encryption
        )
        return metadata

def serialize_metadata_to_bytes(metadata: ProvenanceMetadata) -> bytes:
    """
    Converts the ProvenanceMetadata Pydantic model to its
    JSON string representation, then encodes to UTF-8 bytes
    for uploading.
     """
     # model_dump_json is Pydantic V2
    return metadata.model_dump_json().encode('utf-8')
