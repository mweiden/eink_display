"""Rendering utilities for composing the e-ink calendar view."""

from .tufte import (
    CalendarEvent,
    RendererConfig,
    TufteDayRenderer,
    assign_label_columns_top,
    assign_overlap_columns,
    compute_density_buckets,
)

__all__ = [
    "CalendarEvent",
    "RendererConfig",
    "TufteDayRenderer",
    "assign_label_columns_top",
    "assign_overlap_columns",
    "compute_density_buckets",
]
