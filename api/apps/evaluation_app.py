#
#  Copyright 2026 The RAG-MedQA Authors. All Rights Reserved.
#
"""Evaluation API routes — dataset & test-case management, run evaluation, view results."""

import logging

from quart import request

from api.apps import current_user, login_required
from api.db.services.evaluation_service import EvaluationService
from api.utils.api_utils import (
    get_data_error_result,
    get_json_result,
    get_request_json,
    server_error_response,
)

# ── Datasets ────────────────────────────────────────────────────────────────


@manager.route("/datasets", methods=["POST"])  # noqa: F821
@login_required
async def create_dataset():
    """Create an evaluation dataset bound to one or more knowledge bases."""
    try:
        req = await get_request_json()
        name = req.get("name", "").strip()
        description = req.get("description", "")
        kb_ids = req.get("kb_ids", [])
        if not name:
            return get_data_error_result(message="name is required")
        if not kb_ids:
            return get_data_error_result(message="kb_ids is required")
        dataset = EvaluationService.create_dataset(
            name=name,
            description=description,
            kb_ids=kb_ids,
            tenant_id=current_user.id,
            user_id=current_user.id,
        )
        return get_json_result(data=dataset)
    except Exception as e:
        return server_error_response(e)


@manager.route("/datasets", methods=["GET"])  # noqa: F821
@login_required
def list_datasets():
    """List evaluation datasets with pagination."""
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
        orderby = request.args.get("orderby", "create_time")
        desc = request.args.get("desc", "true").lower() != "false"
        datasets = EvaluationService.list_datasets(
            tenant_id=current_user.id,
            user_id=current_user.id,
            page_number=page,
            items_per_page=page_size,
            orderby=orderby,
            desc=desc,
        )
        return get_json_result(data=datasets)
    except Exception as e:
        return server_error_response(e)


@manager.route("/datasets/<dataset_id>", methods=["GET"])  # noqa: F821
@login_required
def get_dataset(dataset_id: str):
    """Get a single evaluation dataset with its test cases."""
    try:
        dataset = EvaluationService.get_dataset(dataset_id)
        if not dataset:
            return get_data_error_result(message="Dataset not found")
        test_cases = EvaluationService.get_test_cases(dataset_id)
        dataset["test_cases"] = test_cases
        return get_json_result(data=dataset)
    except Exception as e:
        return server_error_response(e)


@manager.route("/datasets/<dataset_id>", methods=["PUT"])  # noqa: F821
@login_required
async def update_dataset(dataset_id: str):
    """Update dataset name or description."""
    try:
        req = await get_request_json()
        ok = EvaluationService.update_dataset(dataset_id, **req)
        if not ok:
            return get_data_error_result(message="Update failed")
        return get_json_result(data={"id": dataset_id})
    except Exception as e:
        return server_error_response(e)


@manager.route("/datasets/<dataset_id>", methods=["DELETE"])  # noqa: F821
@login_required
def delete_dataset(dataset_id: str):
    """Soft-delete an evaluation dataset."""
    try:
        ok = EvaluationService.delete_dataset(dataset_id)
        if not ok:
            return get_data_error_result(message="Delete failed")
        return get_json_result(data={"id": dataset_id})
    except Exception as e:
        return server_error_response(e)


# ── Test Cases ──────────────────────────────────────────────────────────────


@manager.route("/datasets/<dataset_id>/cases", methods=["POST"])  # noqa: F821
@login_required
async def add_test_case(dataset_id: str):
    """Add a single test case."""
    try:
        req = await get_request_json()
        question = req.get("question", "").strip()
        if not question:
            return get_data_error_result(message="question is required")
        case = EvaluationService.add_test_case(
            dataset_id=dataset_id,
            question=question,
            reference_answer=req.get("reference_answer", ""),
            relevant_chunk_ids=req.get("relevant_chunk_ids", []),
            relevant_doc_ids=req.get("relevant_doc_ids", []),
            metadata=req.get("metadata", {}),
        )
        return get_json_result(data=case)
    except Exception as e:
        return server_error_response(e)


@manager.route("/datasets/<dataset_id>/cases/import", methods=["POST"])  # noqa: F821
@login_required
async def import_test_cases(dataset_id: str):
    """Bulk-import test cases (JSON array)."""
    try:
        req = await get_request_json()
        cases = req.get("cases", [])
        if not cases or not isinstance(cases, list):
            return get_data_error_result(message="cases must be a non-empty list")
        success, failed = EvaluationService.import_test_cases(dataset_id, cases)
        return get_json_result(data={"success": success, "failed": failed})
    except Exception as e:
        return server_error_response(e)


@manager.route("/datasets/<dataset_id>/cases/<case_id>", methods=["DELETE"])  # noqa: F821
@login_required
def delete_test_case(dataset_id: str, case_id: str):
    """Delete a single test case."""
    try:
        ok = EvaluationService.delete_test_case(case_id)
        if not ok:
            return get_data_error_result(message="Delete failed")
        return get_json_result(data={"id": case_id})
    except Exception as e:
        return server_error_response(e)


# ── Evaluation Runs ─────────────────────────────────────────────────────────


@manager.route("/runs", methods=["POST"])  # noqa: F821
@login_required
async def start_evaluation():
    """Start an evaluation run against a dialog."""
    try:
        req = await get_request_json()
        dataset_id = req.get("dataset_id")
        dialog_id = req.get("dialog_id")
        if not dataset_id or not dialog_id:
            return get_data_error_result(message="dataset_id and dialog_id are required")
        run = EvaluationService.start_evaluation(
            dataset_id=dataset_id,
            dialog_id=dialog_id,
            tenant_id=current_user.id,
            user_id=current_user.id,
        )
        return get_json_result(data=run)
    except Exception as e:
        return server_error_response(e)


@manager.route("/runs", methods=["GET"])  # noqa: F821
@login_required
def list_runs():
    """List evaluation runs."""
    try:
        runs = EvaluationService.list_datasets(
            tenant_id=current_user.id,
            user_id=current_user.id,
            page_number=int(request.args.get("page", 1)),
            items_per_page=int(request.args.get("page_size", 20)),
        )
        return get_json_result(data=runs)
    except Exception as e:
        return server_error_response(e)


@manager.route("/runs/<run_id>", methods=["GET"])  # noqa: F821
@login_required
def get_run(run_id: str):
    """Get evaluation run results with per-case metrics."""
    try:
        results = EvaluationService.get_run_results(run_id)
        return get_json_result(data=results)
    except Exception as e:
        return server_error_response(e)


@manager.route("/runs/<run_id>/recommendations", methods=["GET"])  # noqa: F821
@login_required
def get_recommendations(run_id: str):
    """Get configuration recommendations based on run results."""
    try:
        recs = EvaluationService.get_recommendations(run_id)
        return get_json_result(data=recs)
    except Exception as e:
        return server_error_response(e)
