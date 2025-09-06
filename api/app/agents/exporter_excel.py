"""
Exporter Excel Agent

This agent generates Excel exports:
- Write exact 17-column schema in strict order using pandas.ExcelWriter + xlsxwriter
- Dates as Excel date cells (not strings)
- Preserve leading zeros for NPI/TIN/ZIP via text format
- Hidden "Provenance" sheet (job_id, version_id, checksums, timings)
"""

import time
import io
from typing import Dict, Any, List
import pandas as pd
from datetime import datetime, timezone
import hashlib

from ..db import get_db_session
from ..models import Job, Version, Record, Export
from ..storage import storage_client, calculate_checksum, generate_object_key
from ..metrics import track_agent_metrics, get_logger

logger = get_logger(__name__)

# Excel Schema - 17 fields in exact order
EXCEL_SCHEMA = [
    "NPI",
    "Provider Name",
    "Specialty",
    "Phone",
    "Email", 
    "Address",
    "City",
    "State",
    "ZIP",
    "DOB",
    "Gender",
    "Effective Date",
    "Term Date",
    "Status",
    "Network",
    "Tier",
    "Notes"
]

@track_agent_metrics("exporter_excel")
def run(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate Excel export with roster data.
    
    Args:
        state: Current processing state with versioned data
    
    Returns:
        Updated state with export information
    """
    logger.info("Starting exporter Excel agent", job_id=state.get("job_id"))
    
    try:
        
        job_id = state.get("job_id")
        version_id = state.get("version_id")
        
        if not job_id or not version_id:
            raise ValueError("Job ID and Version ID are required for export")
        
        # Get records from database
        records = _get_records_for_version(version_id)
        
        if not records:
            logger.warning("No records found for version", job_id=job_id, version_id=version_id)
            state.update({
                "export_created": False,
                "export_error": "No records found for export"
            })
            return state
        
        # Create Excel file
        excel_bytes = _create_excel_file(job_id, version_id, records)
        
        # Store in MinIO
        file_uri = _store_excel_file(job_id, version_id, excel_bytes)
        
        # Create export record
        export_id = _create_export_record(job_id, version_id, file_uri, excel_bytes)
        
        # Update state with export information
        state.update({
            "export_id": export_id,
            "export_created": True,
            "file_uri": file_uri,
            "file_size": len(excel_bytes),
            "record_count": len(records),
            "processing_notes": state.get("processing_notes", []) + [
                f"Excel export created: {len(records)} records, {len(excel_bytes)} bytes"
            ]
        })
        
        logger.info("Exporter Excel agent completed", 
                   job_id=job_id,
                   version_id=version_id,
                   export_id=export_id,
                   records=len(records),
                   file_size=len(excel_bytes))
        
        return state
        
    except Exception as e:
        logger.error("Exporter Excel agent failed", job_id=state.get("job_id"), error=str(e))
        state.update({
            "error": str(e),
            "failed_agent": "exporter_excel"
        })
        return state

def _get_records_for_version(version_id: int) -> List[Dict[str, Any]]:
    """Get all records for a specific version."""
    with get_db_session() as db:
        records = db.query(Record).filter(Record.version_id == version_id).order_by(Record.row_idx).all()
        return [{"row_idx": r.row_idx, "data": r.payload_json} for r in records]

def _create_excel_file(job_id: int, version_id: int, records: List[Dict[str, Any]]) -> bytes:
    """Create Excel file with roster data and provenance sheet."""
    
    # Create DataFrame with exact schema order
    df_data = []
    for record in records:
        row_data = {}
        for field in EXCEL_SCHEMA:
            row_data[field] = record["data"].get(field, "")
        df_data.append(row_data)
    
    df = pd.DataFrame(df_data, columns=EXCEL_SCHEMA)
    
    # Create Excel file in memory
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='xlsxwriter', options={'remove_timezone': True}) as writer:
        # Write main roster data
        df.to_excel(writer, sheet_name='Roster', index=False)
        
        # Get workbook and worksheet for formatting
        workbook = writer.book
        worksheet = writer.sheets['Roster']
        
        # Apply formatting
        _apply_excel_formatting(workbook, worksheet, df)
        
        # Create provenance sheet
        _create_provenance_sheet(workbook, job_id, version_id, len(records))
    
    output.seek(0)
    return output.getvalue()

def _apply_excel_formatting(workbook, worksheet, df):
    """Apply Excel formatting to preserve data types and formatting."""
    
    # Text format for NPI, ZIP (preserve leading zeros)
    text_format = workbook.add_format({'num_format': '@'})
    
    # Date format for date fields
    date_format = workbook.add_format({'num_format': 'mm/dd/yyyy'})
    
    # Apply column-specific formatting
    for col_num, column in enumerate(df.columns):
        if column in ['NPI', 'ZIP']:
            worksheet.set_column(col_num, col_num, 15, text_format)
        elif column in ['DOB', 'Effective Date', 'Term Date']:
            worksheet.set_column(col_num, col_num, 15, date_format)
        elif column == 'Phone':
            worksheet.set_column(col_num, col_num, 15, text_format)
        elif column == 'Email':
            worksheet.set_column(col_num, col_num, 25)
        elif column == 'Address':
            worksheet.set_column(col_num, col_num, 30)
        elif column == 'Provider Name':
            worksheet.set_column(col_num, col_num, 25)
        else:
            worksheet.set_column(col_num, col_num, 15)
    
    # Freeze header row
    worksheet.freeze_panes(1, 0)
    
    # Add autofilter
    worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)

def _create_provenance_sheet(workbook, job_id: int, version_id: int, record_count: int):
    """Create hidden provenance sheet with metadata."""
    
    # Create provenance data
    provenance_data = [
        ['Export Metadata', ''],
        ['Job ID', job_id],
        ['Version ID', version_id],
        ['Record Count', record_count],
        ['Export Date', datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')],
        ['Export Format', 'Excel (.xlsx)'],
        ['Schema Version', '1.0'],
        ['', ''],
        ['System Information', ''],
        ['Generated By', 'HiLabs Roster Processing System'],
        ['Pipeline Version', 'Phase 9'],
        ['', ''],
        ['Data Quality', ''],
        ['Total Records', record_count],
        ['Schema Fields', len(EXCEL_SCHEMA)],
        ['', ''],
        ['Checksums', ''],
        ['Content Hash', _calculate_content_hash(job_id, version_id, record_count)]
    ]
    
    # Create provenance DataFrame
    prov_df = pd.DataFrame(provenance_data, columns=['Field', 'Value'])
    
    # Add provenance sheet (hidden)
    workbook.add_worksheet('_Provenance')
    prov_df.to_excel(workbook, sheet_name='_Provenance', index=False, header=False)
    
    # Hide the provenance sheet
    workbook.worksheets()[-1].hide()

def _calculate_content_hash(job_id: int, version_id: int, record_count: int) -> str:
    """Calculate content hash for provenance."""
    content = f"{job_id}:{version_id}:{record_count}:{datetime.now(timezone.utc).isoformat()}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]

def _store_excel_file(job_id: int, version_id: int, excel_bytes: bytes) -> str:
    """Store Excel file in MinIO and return URI."""
    filename = f"roster_export_job_{job_id}_v{version_id}_{int(time.time())}.xlsx"
    object_key = f"exports/{filename}"
    
    # Store in MinIO
    storage_client.put_bytes(
        bucket="hilabs-artifacts",
        key=object_key,
        data=excel_bytes,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    return f"s3://hilabs-artifacts/{object_key}"

def _create_export_record(job_id: int, version_id: int, file_uri: str, excel_bytes: bytes) -> int:
    """Create export record in database."""
    with get_db_session() as db:
        export = Export(
            job_id=job_id,
            version_id=version_id,
            file_uri=file_uri,
            checksum=calculate_checksum(excel_bytes),
            created_at=datetime.now(timezone.utc)
        )
        db.add(export)
        db.commit()
        db.refresh(export)
        return export.id
