from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime

from app.config import settings
from app.imap import sync_emails_to_db
from app.parser import process_unprocessed_emails
from app.logger import Logger

logger = Logger.get("scheduler")


class SchedulerManager:
    """定时任务管理器"""

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self._sync_job = None
        self._parse_job = None
        self._notify_job = None
        self._cleanup_job = None

    def start(self):
        """启动定时任务"""
        if self.scheduler.running:
            logger.warning("调度器已在运行中")
            return

        # 邮件同步任务 - 每隔N分钟执行一次
        self._sync_job = self.scheduler.add_job(
            sync_emails_to_db,
            trigger=IntervalTrigger(minutes=settings.CHECK_INTERVAL_MINUTES),
            id="sync_emails",
            name="同步邮件",
            replace_existing=True
        )

        # 邮件解析任务 - 每隔5分钟执行一次
        self._parse_job = self.scheduler.add_job(
            process_unprocessed_emails,
            trigger=IntervalTrigger(minutes=5),
            id="parse_emails",
            name="解析邮件",
            replace_existing=True
        )

        # 定时推送任务 - 每天固定时间执行
        self._notify_job = self.scheduler.add_job(
            self._send_daily_summary,
            trigger=CronTrigger(
                hour=settings.SCHEDULED_SEND_HOUR,
                minute=settings.SCHEDULED_SEND_MINUTE
            ),
            id="daily_notification",
            name="每日摘要推送",
            replace_existing=True
        )

        # 日志清理任务 - 每3天执行一次
        self._cleanup_job = self.scheduler.add_job(
            self._cleanup_logs,
            trigger=IntervalTrigger(days=3),
            id="cleanup_logs",
            name="清理旧日志",
            replace_existing=True
        )

        self.scheduler.start()
        logger.info("定时任务调度器已启动")

    def stop(self):
        """停止定时任务"""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=True)
            logger.info("定时任务调度器已停止")

    def _send_daily_summary(self):
        """发送每日摘要"""
        logger.info("执行每日摘要推送任务")
        from app.mailer import mailer
        mailer.send_daily_summary()

    def _cleanup_logs(self):
        """清理旧日志"""
        logger.info("执行日志清理任务")
        from app.logger import Logger
        Logger.cleanup_old_logs(days=3)

    def get_jobs(self):
        """获取所有定时任务"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run_time": str(job.next_run_time) if job.next_run_time else None
            })
        return jobs

    def trigger_sync(self):
        """手动触发邮件同步"""
        return sync_emails_to_db()

    def trigger_parse(self):
        """手动触发邮件解析"""
        return process_unprocessed_emails()


# 全局调度器实例
scheduler = SchedulerManager()
