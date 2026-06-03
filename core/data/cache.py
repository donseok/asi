"""Parquet 기반 디스크 캐시 + 신선도 추적.

설계안 §3-1: MVP는 별도 DB 없이 Parquet + pandas로 충분.
모든 화면에 '데이터 기준일'과 별도로 '마지막 성공 갱신 시각'을 표기하기 위해
파일 mtime을 신선도 기준으로 사용한다.
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

import config


def _path(key: str) -> Path:
    # key에 경로 구분자가 섞이지 않도록 안전화
    safe = key.replace("/", "_").replace("\\", "_")
    return config.CACHE_DIR / f"{safe}.parquet"


def is_fresh(key: str, ttl_hours: float = config.CACHE_TTL_HOURS) -> bool:
    """캐시가 존재하고 TTL 이내면 True."""
    p = _path(key)
    if not p.exists():
        return False
    age_seconds = time.time() - p.stat().st_mtime
    return age_seconds < ttl_hours * 3600


def load(key: str) -> Optional[pd.DataFrame]:
    """캐시를 읽는다. 없으면 None."""
    p = _path(key)
    if p.exists():
        try:
            return pd.read_parquet(p)
        except Exception:
            # 손상된 캐시는 무시하고 재수집하도록 None 반환
            return None
    return None


def save(key: str, df: pd.DataFrame) -> None:
    df.to_parquet(_path(key))


def last_updated(key: str) -> Optional[datetime]:
    """캐시 파일의 마지막 갱신 시각(파이프라인 성공 시각 대용)."""
    p = _path(key)
    if p.exists():
        return datetime.fromtimestamp(p.stat().st_mtime)
    return None


def clear(key: str) -> None:
    p = _path(key)
    if p.exists():
        p.unlink()
