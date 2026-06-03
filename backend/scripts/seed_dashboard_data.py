import sys
import os
import asyncio
import datetime
import json
import random

# Add backend directory to PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.database import engine, Base, async_session
from app.db.models import User, ProcessingJob, AuditLog
from app.security.hashing import get_password_hash

async def seed_data():
    print("Seeding dashboard data...")
    
    # 1. Initialize DB tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    async with async_session() as session:
        # 2. Get or create pragya operator user
        username = "pragya"
        password = "deal@123"
        user = None
        
        # Check if exists
        from sqlalchemy import select
        res = await session.execute(select(User).where(User.username == username))
        user = res.scalar_one_or_none()
        
        if not user:
            print(f"Creating user '{username}'...")
            password_hash = get_password_hash(password)
            user = User(username=username, password_hash=password_hash, role="admin")
            session.add(user)
            await session.commit()
            await session.refresh(user)
        else:
            print(f"User '{username}' already exists.")
            
        # 3. Clear existing processing jobs to start fresh
        from sqlalchemy import delete
        await session.execute(delete(ProcessingJob))
        await session.execute(delete(AuditLog))
        await session.commit()
        
        # 4. Insert 12 sample processing jobs spanning the last 7 days
        noise_types = ["static", "rotor", "crowd", "wind", "engine"]
        today = datetime.datetime.utcnow()
        
        jobs_to_seed = []
        
        # Let's seed 10 completed, 1 pending, 1 failed job
        # 10 completed jobs
        for i in range(10):
            # dates from 6 days ago to today
            day_offset = random.randint(0, 6)
            hour_offset = random.randint(0, 23)
            min_offset = random.randint(0, 59)
            job_date = today - datetime.timedelta(days=day_offset, hours=hour_offset, minutes=min_offset)
            
            pre_snr = round(random.uniform(-5.0, 8.0), 2)
            improvement = round(random.uniform(8.0, 18.0), 2)
            post_snr = round(pre_snr + improvement, 2)
            
            pre_ovr = round(random.uniform(1.5, 2.8), 2)
            post_ovr = round(pre_ovr + random.uniform(0.5, 1.2), 2)
            post_sig = round(post_ovr + random.uniform(0.1, 0.4), 2)
            post_bak = round(post_ovr - random.uniform(0.1, 0.4), 2)
            
            noise_class = random.choice(noise_types)
            latency = round(random.uniform(80.0, 160.0), 2)
            
            metrics = {
                "pre_snr_db": pre_snr,
                "post_snr_db": post_snr,
                "snr_improvement_db": improvement,
                "pre_dnsmos": {"sig": pre_ovr + 0.2, "bak": pre_ovr - 0.2, "ovr": pre_ovr},
                "post_dnsmos": {"sig": post_sig, "bak": post_bak, "ovr": post_ovr},
                "dnsmos_improvement_ovr": round(post_ovr - pre_ovr, 2),
                "confidence_score": round(random.uniform(75.0, 95.0), 1),
                "confidence_status": "High",
                "speaker_similarity": round(random.uniform(0.82, 0.96), 3),
                "noise_class": noise_class,
                "noise_probability": round(random.uniform(0.70, 0.99), 2),
                "noise_explanation": f"Detected high levels of {noise_class} background noise.",
                "latency_ms": latency
            }
            
            job = ProcessingJob(
                user_id=user.id,
                status="completed",
                input_path=f"test_noisy_{i:04d}.wav",
                output_path=f"enhanced_test_noisy_{i:04d}.wav.enc",
                input_hash=f"hash_in_{i}",
                output_hash=f"hash_out_{i}",
                model_version="catr-se-v0.1-hybrid",
                metrics_json=json.dumps(metrics),
                pre_snr_db=pre_snr,
                post_snr_db=post_snr,
                noise_classification=noise_class,
                created_at=job_date
            )
            jobs_to_seed.append(job)
            
        # Add 1 pending job
        pending_job = ProcessingJob(
            user_id=user.id,
            status="pending",
            input_path="pending_file.wav",
            input_hash="hash_pending",
            created_at=today - datetime.timedelta(minutes=10)
        )
        jobs_to_seed.append(pending_job)
        
        # Add 1 failed job
        failed_job = ProcessingJob(
            user_id=user.id,
            status="failed",
            input_path="corrupt_audio.wav",
            input_hash="hash_corrupt",
            created_at=today - datetime.timedelta(hours=2)
        )
        jobs_to_seed.append(failed_job)
        
        session.add_all(jobs_to_seed)
        await session.commit()
        print(f"Successfully seeded {len(jobs_to_seed)} jobs.")
        
        # 5. Seed some audit logs
        audit_logs = [
            AuditLog(user_id=user.id, action="login", created_at=today - datetime.timedelta(days=3)),
            AuditLog(user_id=user.id, action="process_file_sync", details_json=json.dumps({"filename": "test_noisy_0001.wav"}), created_at=today - datetime.timedelta(days=2)),
            AuditLog(user_id=user.id, action="run_benchmark", details_json=json.dumps({"dataset_version": "catr_radio_v0.1"}), created_at=today - datetime.timedelta(days=1)),
            AuditLog(user_id=user.id, action="audit_view", created_at=today - datetime.timedelta(hours=1))
        ]
        session.add_all(audit_logs)
        await session.commit()
        print("Successfully seeded audit logs.")

if __name__ == "__main__":
    asyncio.run(seed_data())
