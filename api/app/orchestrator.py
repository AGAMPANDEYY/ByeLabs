"""
LangGraph Orchestrator

This module implements a stateful DAG using LangGraph to orchestrate the multi-agent
pipeline with conditional branches, checkpoints, and resumable execution.
"""

import time
from typing import Dict, Any, List, Optional, Literal, Annotated
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
import structlog

from .db import get_db_session
from .models import Job, Version, Record, Issue, Export, JobStatus, IssueLevel
from .storage import calculate_checksum, generate_object_key
from .agents import (
    intake_email_run,
    classifier_run,
    extract_rule_run,
    extract_pdf_run,
    vlm_client_run,
    normalizer_run,
    validator_run,
    versioner_run,
    exporter_excel_run
)

logger = structlog.get_logger(__name__)

# ============================================================================
# STATE MODEL
# ============================================================================

class ProcessingState(BaseModel):
    """State model for the LangGraph orchestrator."""
    
    # Core identifiers
    job_id: int
    version_id: Optional[int] = None
    
    # Artifacts and data
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    route_map: Dict[str, Any] = Field(default_factory=dict)
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Processing flags
    needs_vlm: bool = False
    vlm_used: bool = False
    force_vlm_toggle: bool = False
    
    # Results and issues
    issues: List[Dict[str, Any]] = Field(default_factory=list)
    status: Literal["pending", "processing", "needs_review", "ready", "failed"] = "pending"
    
    # Processing metadata
    processing_notes: List[str] = Field(default_factory=list)
    start_time: Optional[float] = None
    checkpoint_data: Dict[str, Any] = Field(default_factory=dict)
    
    # Error handling
    error: Optional[str] = None
    failed_agent: Optional[str] = None

# ============================================================================
# NODE FUNCTIONS
# ============================================================================

def intake_node(state: ProcessingState) -> ProcessingState:
    """Intake node - parse email and prepare for processing."""
    logger.info("Running intake node", job_id=state.job_id)
    
    try:
        # Convert state to dict for agent compatibility
        agent_state = {
            "job_id": state.job_id,
            "processing_notes": state.processing_notes,
            "start_time": state.start_time or time.time()
        }
        
        # Run intake agent
        result = intake_email_run(agent_state)
        
        # Update state
        state.artifacts.update(result.get("artifacts", {}))
        state.processing_notes = result.get("processing_notes", [])
        
        if result.get("error"):
            state.error = result["error"]
            state.failed_agent = "intake_email"
            state.status = "failed"
        
        logger.info("Intake node completed", job_id=state.job_id)
        return state
        
    except Exception as e:
        logger.error("Intake node failed", job_id=state.job_id, error=str(e))
        state.error = str(e)
        state.failed_agent = "intake"
        state.status = "failed"
        return state

def classify_node(state: ProcessingState) -> ProcessingState:
    """Classify node - determine processing strategy."""
    logger.info("Running classify node", job_id=state.job_id)
    
    try:
        # Convert state to dict for agent compatibility
        agent_state = {
            "job_id": state.job_id,
            "processing_notes": state.processing_notes,
            "artifacts": state.artifacts
        }
        
        # Run classifier agent
        result = classifier_run(agent_state)
        
        # Update state with classification results
        classification = result.get("classification", {})
        state.route_map = classification
        state.needs_vlm = classification.get("requires_vlm", False)
        state.processing_notes = result.get("processing_notes", [])
        
        if result.get("error"):
            state.error = result["error"]
            state.failed_agent = "classifier"
            state.status = "failed"
        
        logger.info("Classify node completed", job_id=state.job_id, needs_vlm=state.needs_vlm)
        return state
        
    except Exception as e:
        logger.error("Classify node failed", job_id=state.job_id, error=str(e))
        state.error = str(e)
        state.failed_agent = "classify"
        state.status = "failed"
        return state

def extract_node(state: ProcessingState) -> ProcessingState:
    """Extract node - perform rule-based and PDF extraction."""
    logger.info("Running extract node", job_id=state.job_id)
    
    try:
        # Convert state to dict for agent compatibility
        agent_state = {
            "job_id": state.job_id,
            "processing_notes": state.processing_notes,
            "artifacts": state.artifacts,
            "route_map": state.route_map
        }
        
        # Run extract rule agent
        result = extract_rule_run(agent_state)
        if result.get("error"):
            raise Exception(f"Extract rule failed: {result['error']}")
        
        # Run extract PDF agent
        result = extract_pdf_run(result)
        if result.get("error"):
            raise Exception(f"Extract PDF failed: {result['error']}")
        
        # Update state with extracted data
        state.rows = result.get("extracted_data", [])
        state.processing_notes = result.get("processing_notes", [])
        
        # Store checkpoint data
        state.checkpoint_data["extract"] = {
            "rows": state.rows,
            "timestamp": time.time()
        }
        
        logger.info("Extract node completed", job_id=state.job_id, rows_count=len(state.rows))
        return state
        
    except Exception as e:
        logger.error("Extract node failed", job_id=state.job_id, error=str(e))
        state.error = str(e)
        state.failed_agent = "extract"
        state.status = "failed"
        return state

def vlm_assist_node(state: ProcessingState) -> ProcessingState:
    """VLM assist node - use Vision Language Model for complex extraction."""
    logger.info("Running VLM assist node", job_id=state.job_id)
    
    try:
        # Convert state to dict for agent compatibility
        agent_state = {
            "job_id": state.job_id,
            "processing_notes": state.processing_notes,
            "artifacts": state.artifacts,
            "route_map": state.route_map,
            "extracted_data": state.rows
        }
        
        # Run VLM client agent
        result = vlm_client_run(agent_state)
        
        # Update state with VLM results
        vlm_data = result.get("vlm_data", {})
        if vlm_data.get("extracted_data"):
            state.rows = vlm_data["extracted_data"]
            state.vlm_used = True
        
        state.processing_notes = result.get("processing_notes", [])
        
        # Store checkpoint data
        state.checkpoint_data["vlm_assist"] = {
            "rows": state.rows,
            "vlm_used": state.vlm_used,
            "timestamp": time.time()
        }
        
        if result.get("error"):
            state.error = result["error"]
            state.failed_agent = "vlm_client"
            state.status = "failed"
        
        logger.info("VLM assist node completed", job_id=state.job_id, vlm_used=state.vlm_used)
        return state
        
    except Exception as e:
        logger.error("VLM assist node failed", job_id=state.job_id, error=str(e))
        state.error = str(e)
        state.failed_agent = "vlm_assist"
        state.status = "failed"
        return state

def normalize_node(state: ProcessingState) -> ProcessingState:
    """Normalize node - clean and standardize extracted data."""
    logger.info("Running normalize node", job_id=state.job_id)
    
    try:
        # Convert state to dict for agent compatibility
        agent_state = {
            "job_id": state.job_id,
            "processing_notes": state.processing_notes,
            "extracted_data": state.rows
        }
        
        # Run normalizer agent
        result = normalizer_run(agent_state)
        
        # Update state with normalized data
        state.rows = result.get("normalized_data", state.rows)
        state.processing_notes = result.get("processing_notes", [])
        
        # Store checkpoint data
        state.checkpoint_data["normalize"] = {
            "rows": state.rows,
            "timestamp": time.time()
        }
        
        if result.get("error"):
            state.error = result["error"]
            state.failed_agent = "normalizer"
            state.status = "failed"
        
        logger.info("Normalize node completed", job_id=state.job_id, rows_count=len(state.rows))
        return state
        
    except Exception as e:
        logger.error("Normalize node failed", job_id=state.job_id, error=str(e))
        state.error = str(e)
        state.failed_agent = "normalize"
        state.status = "failed"
        return state

def validate_node(state: ProcessingState) -> ProcessingState:
    """Validate node - check data quality and generate issues."""
    logger.info("Running validate node", job_id=state.job_id)
    
    try:
        # Convert state to dict for agent compatibility
        agent_state = {
            "job_id": state.job_id,
            "processing_notes": state.processing_notes,
            "normalized_data": state.rows
        }
        
        # Run validator agent
        result = validator_run(agent_state)
        
        # Update state with validation results
        state.issues = result.get("validation_issues", [])
        state.processing_notes = result.get("processing_notes", [])
        
        # Check if validation passed
        validation_stats = result.get("validation_stats", {})
        error_count = validation_stats.get("error_count", 0)
        
        if error_count > 0:
            state.status = "needs_review"
            logger.info("Validation found errors, stopping for review", job_id=state.job_id, error_count=error_count)
        else:
            logger.info("Validation passed, continuing to version", job_id=state.job_id)
        
        if result.get("error"):
            state.error = result["error"]
            state.failed_agent = "validator"
            state.status = "failed"
        
        return state
        
    except Exception as e:
        logger.error("Validate node failed", job_id=state.job_id, error=str(e))
        state.error = str(e)
        state.failed_agent = "validate"
        state.status = "failed"
        return state

def version_node(state: ProcessingState) -> ProcessingState:
    """Version node - create new version with validated data."""
    logger.info("Running version node", job_id=state.job_id)
    
    try:
        # Convert state to dict for agent compatibility
        agent_state = {
            "job_id": state.job_id,
            "processing_notes": state.processing_notes,
            "validated_data": state.rows,
            "validation_issues": state.issues
        }
        
        # Run versioner agent
        result = versioner_run(agent_state)
        
        # Update state with version info
        version_info = result.get("version_info", {})
        state.version_id = version_info.get("version_id")
        state.processing_notes = result.get("processing_notes", [])
        
        if result.get("error"):
            state.error = result["error"]
            state.failed_agent = "versioner"
            state.status = "failed"
        
        logger.info("Version node completed", job_id=state.job_id, version_id=state.version_id)
        return state
        
    except Exception as e:
        logger.error("Version node failed", job_id=state.job_id, error=str(e))
        state.error = str(e)
        state.failed_agent = "version"
        state.status = "failed"
        return state

def export_node(state: ProcessingState) -> ProcessingState:
    """Export node - generate Excel export."""
    logger.info("Running export node", job_id=state.job_id)
    
    try:
        # Convert state to dict for agent compatibility
        agent_state = {
            "job_id": state.job_id,
            "processing_notes": state.processing_notes,
            "version_info": {"version_id": state.version_id},
            "validated_data": state.rows
        }
        
        # Run exporter agent
        result = exporter_excel_run(agent_state)
        
        # Update state with export info
        state.artifacts["excel_export"] = result.get("excel_export", {})
        state.processing_notes = result.get("processing_notes", [])
        state.status = "ready"
        
        if result.get("error"):
            state.error = result["error"]
            state.failed_agent = "exporter_excel"
            state.status = "failed"
        
        logger.info("Export node completed", job_id=state.job_id, status=state.status)
        return state
        
    except Exception as e:
        logger.error("Export node failed", job_id=state.job_id, error=str(e))
        state.error = str(e)
        state.failed_agent = "export"
        state.status = "failed"
        return state

# ============================================================================
# CONDITIONAL EDGES
# ============================================================================

def should_use_vlm(state: ProcessingState) -> str:
    """Determine if VLM assistance is needed."""
    if state.needs_vlm or state.force_vlm_toggle:
        return "vlm_assist"
    else:
        return "normalize"

def should_continue_after_validate(state: ProcessingState) -> str:
    """Determine if processing should continue after validation."""
    if state.status == "needs_review":
        return END
    else:
        return "version"

# ============================================================================
# GRAPH CONSTRUCTION
# ============================================================================

def create_processing_graph() -> StateGraph:
    """Create the LangGraph processing workflow."""
    
    # Create the state graph
    workflow = StateGraph(ProcessingState)
    
    # Add nodes
    workflow.add_node("intake", intake_node)
    workflow.add_node("classify", classify_node)
    workflow.add_node("extract", extract_node)
    workflow.add_node("vlm_assist", vlm_assist_node)
    workflow.add_node("normalize", normalize_node)
    workflow.add_node("validate", validate_node)
    workflow.add_node("version", version_node)
    workflow.add_node("export", export_node)
    
    # Add edges
    workflow.set_entry_point("intake")
    workflow.add_edge("intake", "classify")
    workflow.add_edge("classify", "extract")
    workflow.add_conditional_edges(
        "extract",
        should_use_vlm,
        {
            "vlm_assist": "vlm_assist",
            "normalize": "normalize"
        }
    )
    workflow.add_edge("vlm_assist", "normalize")
    workflow.add_edge("normalize", "validate")
    workflow.add_conditional_edges(
        "validate",
        should_continue_after_validate,
        {
            "version": "version",
            END: END
        }
    )
    workflow.add_edge("version", "export")
    workflow.add_edge("export", END)
    
    # Add checkpoints
    memory = MemorySaver()
    workflow = workflow.compile(checkpointer=memory)
    
    return workflow

# ============================================================================
# ORCHESTRATOR FUNCTIONS
# ============================================================================

def run_graph(job_id: int) -> Dict[str, Any]:
    """
    Execute the processing graph from start to completion or needs_review.
    
    Args:
        job_id: The job ID to process
    
    Returns:
        Processing result with status and metadata
    """
    logger.info("Starting graph execution", job_id=job_id)
    
    try:
        # Create initial state
        initial_state = ProcessingState(
            job_id=job_id,
            start_time=time.time(),
            status="processing"
        )
        
        # Create and run the graph
        workflow = create_processing_graph()
        
        # Execute the graph
        final_state = workflow.invoke(initial_state)
        
        # Persist results to database
        _persist_graph_results(final_state)
        
        # Prepare result
        result = {
            "job_id": job_id,
            "status": final_state.status,
            "version_id": final_state.version_id,
            "processing_time": time.time() - final_state.start_time,
            "rows_processed": len(final_state.rows),
            "issues_found": len(final_state.issues),
            "vlm_used": final_state.vlm_used,
            "processing_notes": final_state.processing_notes
        }
        
        if final_state.error:
            result["error"] = final_state.error
            result["failed_agent"] = final_state.failed_agent
        
        logger.info("Graph execution completed", **result)
        return result
        
    except Exception as e:
        logger.error("Graph execution failed", job_id=job_id, error=str(e))
        return {
            "job_id": job_id,
            "status": "failed",
            "error": str(e),
            "processing_time": time.time() - (initial_state.start_time if 'initial_state' in locals() else time.time())
        }

def resume_graph(job_id: int, version_id: int) -> Dict[str, Any]:
    """
    Resume graph execution from the validate node.
    
    Args:
        job_id: The job ID to resume
        version_id: The version ID to resume from
    
    Returns:
        Processing result with status and metadata
    """
    logger.info("Resuming graph execution", job_id=job_id, version_id=version_id)
    
    try:
        # Load existing state from database
        with get_db_session() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found")
            
            version = db.query(Version).filter(Version.id == version_id).first()
            if not version:
                raise ValueError(f"Version {version_id} not found")
            
            # Load existing data
            records = db.query(Record).filter(Record.version_id == version_id).all()
            issues = db.query(Issue).filter(Issue.version_id == version_id).all()
            
            # Reconstruct state
            state = ProcessingState(
                job_id=job_id,
                version_id=version_id,
                rows=[{"row_idx": r.row_idx, "data": r.payload_json} for r in records],
                issues=[{"row_idx": i.row_idx, "field": i.field, "level": i.level, "message": i.message} for i in issues],
                status="processing"
            )
        
        # Create and run the graph from validate node
        workflow = create_processing_graph()
        
        # Resume from validate node
        final_state = workflow.invoke(state, {"configurable": {"thread_id": f"job_{job_id}"}})
        
        # Persist results to database
        _persist_graph_results(final_state)
        
        # Prepare result
        result = {
            "job_id": job_id,
            "status": final_state.status,
            "version_id": final_state.version_id,
            "resumed": True,
            "rows_processed": len(final_state.rows),
            "issues_found": len(final_state.issues),
            "processing_notes": final_state.processing_notes
        }
        
        logger.info("Graph resume completed", **result)
        return result
        
    except Exception as e:
        logger.error("Graph resume failed", job_id=job_id, error=str(e))
        return {
            "job_id": job_id,
            "status": "failed",
            "error": str(e),
            "resumed": True
        }

def _persist_graph_results(state: ProcessingState) -> None:
    """Persist graph results to database."""
    try:
        with get_db_session() as db:
            job = db.query(Job).filter(Job.id == state.job_id).first()
            if not job:
                return
            
            # Update job status
            job.status = JobStatus.READY if state.status == "ready" else JobStatus.NEEDS_REVIEW if state.status == "needs_review" else JobStatus.FAILED
            
            # Create version if not exists
            if not state.version_id:
                version = Version(
                    job_id=state.job_id,
                    author="system",
                    reason="LangGraph orchestrated processing"
                )
                db.add(version)
                db.flush()
                state.version_id = version.id
            
            # Store records
            for row in state.rows:
                record = Record(
                    job_id=state.job_id,
                    version_id=state.version_id,
                    row_idx=row["row_idx"],
                    payload_json=row["data"]
                )
                db.add(record)
            
            # Store issues
            for issue in state.issues:
                issue_record = Issue(
                    version_id=state.version_id,
                    row_idx=issue.get("row_idx"),
                    field=issue.get("field"),
                    level=issue["level"],
                    message=issue["message"]
                )
                db.add(issue_record)
            
            # Update job current version
            job.current_version_id = state.version_id
            
            db.commit()
            
    except Exception as e:
        logger.error("Failed to persist graph results", job_id=state.job_id, error=str(e))
        raise
