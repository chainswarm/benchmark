from chainswarm_core.jobs import create_celery_app, run_dev_worker


celery_app = create_celery_app(
    name="benchmark-jobs",
    autodiscover=["packages.jobs.tasks"],
    beat_schedule_path="packages/jobs/beat_schedule.json",
)

def get_celery_app():
    return celery_app

__all__ = ['celery_app', 'get_celery_app']

if __name__ == '__main__':
    run_dev_worker(celery_app)