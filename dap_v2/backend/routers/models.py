"""
DAP v2.0 - Model Management API
AI模型管理API
"""
from fastapi import APIRouter, HTTPException, status
from typing import Optional
from pydantic import BaseModel

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.retraining_pipeline import get_retraining_pipeline

router = APIRouter(prefix="/models", tags=["AI模型管理"])

# 获取重训练管道
pipeline = get_retraining_pipeline()


class RetrainingRequest(BaseModel):
    """重训练请求"""
    model_type: str
    force: bool = False


class ScheduleRequest(BaseModel):
    """调度请求"""
    model_type: str
    schedule: str = "weekly"


@router.get("/")
async def list_models():
    """1. 列出所有模型"""
    result = pipeline.list_all_models()
    return result


@router.get("/{model_type}")
async def get_model_info(model_type: str):
    """2. 获取模型信息"""
    info = pipeline.get_model_info(model_type)
    if not info:
        raise HTTPException(status_code=404, detail="模型不存在")
    return info


@router.get("/{model_type}/check")
async def check_retraining_needed(model_type: str):
    """3. 检查是否需要重训练"""
    result = pipeline.check_retraining_needed(model_type)
    return result


@router.post("/{model_type}/train")
async def trigger_retraining(model_type: str, force: bool = False):
    """4. 触发模型重训练"""
    # 检查是否需要重训练
    if not force:
        check_result = pipeline.check_retraining_needed(model_type)
        if not check_result['needed']:
            return {
                'message': '暂不需要重训练',
                'reason': check_result['reason'],
                'sample_count': check_result['sample_count']
            }

    # 加载训练样本
    samples = pipeline.load_training_samples(model_type)

    if not samples:
        raise HTTPException(status_code=400, detail="没有可用的训练样本")

    # 根据模型类型训练
    if model_type == 'classification':
        result = pipeline.train_evidence_classification_model(samples)
    elif model_type == 'ocr':
        result = pipeline.train_ocr_correction_model(samples)
    else:
        raise HTTPException(status_code=400, detail=f"不支持的模型类型: {model_type}")

    if not result['success']:
        raise HTTPException(status_code=500, detail=result.get('error', '训练失败'))

    return {
        'message': '模型训练完成',
        'result': result
    }


@router.post("/{model_type}/rollback")
async def rollback_model(model_type: str, version: int):
    """5. 回滚模型到指定版本"""
    result = pipeline.rollback_model(model_type, version)

    if not result['success']:
        raise HTTPException(status_code=500, detail=result.get('error', '回滚失败'))

    return result


@router.get("/{model_type}/compare")
async def compare_models(
    model_type: str,
    version_a: int,
    version_b: int
):
    """6. 比较两个模型版本 (A/B测试)"""
    result = pipeline.compare_models(model_type, version_a, version_b)

    if 'error' in result:
        raise HTTPException(status_code=500, detail=result['error'])

    return result


@router.post("/{model_type}/schedule")
async def schedule_retraining(
    model_type: str,
    schedule: str = "weekly"
):
    """7. 调度定期重训练"""
    result = pipeline.schedule_retraining(model_type, schedule)

    if not result['success']:
        raise HTTPException(status_code=500, detail=result.get('error', '调度失败'))

    return result
