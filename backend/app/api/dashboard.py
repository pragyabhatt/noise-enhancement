import json
import datetime
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import ProcessingJob, User
from app.api.auth import get_current_user
from app.security.rbac import allow_operator

router = APIRouter(prefix="/metrics", tags=["Dashboard"])

@router.get("/dashboard")
async def get_dashboard_metrics(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get KPI metrics and trend data for the system dashboard.
    Restricted to authenticated operators/analysts/admins.
    """
    # Enforce RBAC (operators/analysts/admins can view dashboard)
    allow_operator(current_user)
    
    # 1. Total processed jobs (completed)
    total_query = select(func.count(ProcessingJob.id)).where(ProcessingJob.status == "completed")
    total_res = await db.execute(total_query)
    total_processed = total_res.scalar() or 0
    
    # 2. Avg SNR Improvement and Avg DNSMOS Overall
    avg_query = select(ProcessingJob.pre_snr_db, ProcessingJob.post_snr_db, ProcessingJob.metrics_json).where(ProcessingJob.status == "completed")
    avg_res = await db.execute(avg_query)
    jobs_data = avg_res.all()
    
    avg_snr_improvement = 0.0
    avg_dnsmos_ovr = 0.0
    
    valid_snr_count = 0
    valid_dnsmos_count = 0
    
    for row in jobs_data:
        pre_snr = row[0]
        post_snr = row[1]
        metrics_str = row[2]
        
        if pre_snr is not None and post_snr is not None:
            avg_snr_improvement += (post_snr - pre_snr)
            valid_snr_count += 1
            
        if metrics_str:
            try:
                metrics = json.loads(metrics_str)
                # Handle nested dict: post_dnsmos = {"sig": X, "bak": Y, "ovr": Z}
                post_dnsmos = metrics.get("post_dnsmos", {})
                if isinstance(post_dnsmos, dict):
                    ovr = post_dnsmos.get("ovr")
                    if ovr is not None:
                        avg_dnsmos_ovr += float(ovr)
                        valid_dnsmos_count += 1
            except Exception:
                pass
                
    if valid_snr_count > 0:
        avg_snr_improvement = round(avg_snr_improvement / valid_snr_count, 2)
    else:
        avg_snr_improvement = 0.0
        
    if valid_dnsmos_count > 0:
        avg_dnsmos_ovr = round(avg_dnsmos_ovr / valid_dnsmos_count, 2)
    else:
        avg_dnsmos_ovr = 0.0
        
    # 3. System Status (Uptime placeholder - actual status badge is detailed in layout)
    system_health = "Healthy"
    
    # 4. Recent completed jobs list (latest 5)
    recent_query = select(ProcessingJob).order_by(desc(ProcessingJob.created_at)).limit(5)
    recent_res = await db.execute(recent_query)
    recent_jobs_db = recent_res.scalars().all()
    
    recent_jobs = []
    for job in recent_jobs_db:
        metrics_dict = {}
        if job.metrics_json:
            try:
                metrics_dict = json.loads(job.metrics_json)
            except Exception:
                pass
                
        # Resolve username
        username = "system"
        if job.user_id:
            user_query = select(User.username).where(User.id == job.user_id)
            user_res = await db.execute(user_query)
            username = user_res.scalar() or "system"
            
        recent_jobs.append({
            "id": job.id,
            "filename": job.input_path,
            "status": job.status,
            "pre_snr": round(job.pre_snr_db, 2) if job.pre_snr_db is not None else None,
            "post_snr": round(job.post_snr_db, 2) if job.post_snr_db is not None else None,
            "snr_improvement": round(job.post_snr_db - job.pre_snr_db, 2) if job.post_snr_db is not None and job.pre_snr_db is not None else None,
            "noise_class": job.noise_classification or "unknown",
            "operator": username,
            "created_at": job.created_at
        })
        
    # 5. SNR Trend (grouped by day, last 7 days)
    # We can calculate daily averages from the DB
    trend_data = {}
    today = datetime.datetime.utcnow().date()
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        day_str = day.strftime("%Y-%m-%d")
        trend_data[day_str] = {"pre_snrs": [], "post_snrs": []}
        
    for row in jobs_data:
        pre_snr = row[0]
        post_snr = row[1]
        # In a real environment, we'd filter row's created_at, but we'll do average
        # for dates. Let's get dates dynamically from the query
        pass
        
    # Let's query SNR grouped by date for the last 7 days
    seven_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    trend_query = select(
        ProcessingJob.pre_snr_db,
        ProcessingJob.post_snr_db,
        ProcessingJob.created_at
    ).where(ProcessingJob.status == "completed", ProcessingJob.created_at >= seven_days_ago)
    
    trend_res = await db.execute(trend_query)
    trend_rows = trend_res.all()
    
    for row in trend_rows:
        pre_snr = row[0]
        post_snr = row[1]
        created_at = row[2]
        if created_at and pre_snr is not None and post_snr is not None:
            day_str = created_at.date().strftime("%Y-%m-%d")
            if day_str in trend_data:
                trend_data[day_str]["pre_snrs"].append(pre_snr)
                trend_data[day_str]["post_snrs"].append(post_snr)
                
    snr_trend = []
    for day_str, data in sorted(trend_data.items()):
        pre_list = data["pre_snrs"]
        post_list = data["post_snrs"]
        snr_trend.append({
            "date": day_str,
            "pre_snr": round(sum(pre_list) / len(pre_list), 2) if pre_list else 0.0,
            "post_snr": round(sum(post_list) / len(post_list), 2) if post_list else 0.0
        })
        
    # 6. Noise distribution (counts by noise_classification)
    noise_dist = {
        "static": 0,
        "rotor": 0,
        "crowd": 0,
        "wind": 0,
        "engine": 0,
        "unknown": 0
    }
    
    noise_query = select(ProcessingJob.noise_classification, func.count(ProcessingJob.id)).where(ProcessingJob.status == "completed").group_by(ProcessingJob.noise_classification)
    noise_res = await db.execute(noise_query)
    noise_rows = noise_res.all()
    
    for row in noise_rows:
        n_class = row[0] or "unknown"
        count = row[1] or 0
        if n_class in noise_dist:
            noise_dist[n_class] += count
        else:
            noise_dist["unknown"] += count
            
    noise_distribution = [{"class": k, "count": v} for k, v in noise_dist.items()]
    
    # 7. Latency trend (last 15 jobs)
    latency_query = select(ProcessingJob.id, ProcessingJob.metrics_json).where(ProcessingJob.status == "completed").order_by(desc(ProcessingJob.created_at)).limit(15)
    latency_res = await db.execute(latency_query)
    latency_rows = latency_res.all()
    
    latency_trend = []
    # Reverse so they read left-to-right chronologically
    for row in reversed(latency_rows):
        job_id = row[0]
        metrics_str = row[1]
        lat_ms = 0.0
        if metrics_str:
            try:
                metrics = json.loads(metrics_str)
                lat_ms = float(metrics.get("latency_ms", 0.0))
            except Exception:
                pass
        latency_trend.append({
            "job_id": f"Job #{job_id}",
            "latency_ms": round(lat_ms, 1)
        })
        
    return {
        "total_processed": total_processed,
        "avg_snr_improvement": avg_snr_improvement,
        "avg_dnsmos": avg_dnsmos_ovr,
        "system_health": system_health,
        "recent_jobs": recent_jobs,
        "snr_trend": snr_trend,
        "noise_distribution": noise_distribution,
        "latency_trend": latency_trend
    }
