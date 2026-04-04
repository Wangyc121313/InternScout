"""
通知系统 - 支持邮件、Webhook和RSS订阅
"""
import json
import smtplib
from abc import ABC, abstractmethod
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

import requests

from utils.logger import get_logger

logger = get_logger(__name__)


class Notifier(ABC):
    """通知基类"""

    @abstractmethod
    def send(self, message: Any) -> bool:
        """
        发送通知

        Args:
            message: 消息内容

        Returns:
            是否发送成功
        """
        pass


class EmailNotifier(Notifier):
    """邮件通知器"""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        recipients: List[str],
        use_tls: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.recipients = recipients
        self.use_tls = use_tls

    def _send_email(self, to: str, subject: str, body: str, is_html: bool = False) -> bool:
        """发送单封邮件"""
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.smtp_user
            msg['To'] = to

            content_type = 'html' if is_html else 'plain'
            msg.attach(MIMEText(body, content_type, 'utf-8'))

            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent to {to}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")
            return False

    def send(self, message: Dict[str, Any]) -> bool:
        """
        发送邮件通知

        Args:
            message: 包含 subject, body, is_html 的字典
        """
        subject = message.get('subject', 'InternScout 通知')
        body = message.get('body', '')
        is_html = message.get('is_html', False)

        results = []
        for recipient in self.recipients:
            result = self._send_email(recipient, subject, body, is_html)
            results.append(result)

        return any(results)

    def send_jobs_notification(self, jobs: List[Dict[str, Any]]) -> bool:
        """发送新职位通知"""
        if not jobs:
            return True

        subject = f"InternScout - 新增 {len(jobs)} 个实习职位"

        # 构建HTML内容
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6;">
            <h2>今日新增实习职位</h2>
            <p>共 {len(jobs)} 个新职位</p>
            <hr>
        """

        for job in jobs[:20]:  # 最多显示20条
            html_body += f"""
            <div style="margin-bottom: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 5px;">
                <h3 style="margin: 0 0 10px 0; color: #2563eb;">
                    <a href="{job.get('url', '#')}" style="text-decoration: none; color: #2563eb;">
                        {job.get('title', '未知职位')}
                    </a>
                </h3>
                <p style="margin: 5px 0; color: #666;">
                    <strong>{job.get('company', '未知公司')}</strong> |
                    {job.get('location', '地点不限')} |
                    <span style="color: #f97316;">{job.get('salary', '薪资面议')}</span>
                </p>
                <p style="margin: 5px 0; font-size: 0.9em; color: #888;">
                    来源: {job.get('source', '未知')}
                </p>
            </div>
            """

        if len(jobs) > 20:
            html_body += f"<p>... 还有 {len(jobs) - 20} 个职位</p>"

        html_body += """
            <hr>
            <p style="font-size: 0.9em; color: #666;">
                此邮件由 InternScout 自动发送
            </p>
        </body>
        </html>
        """

        return self.send({
            'subject': subject,
            'body': html_body,
            'is_html': True,
        })


class WebhookNotifier(Notifier):
    """Webhook通知器（支持钉钉、企业微信、飞书等）"""

    def __init__(self, webhook_url: str, webhook_type: str = "dingtalk"):
        self.webhook_url = webhook_url
        self.webhook_type = webhook_type.lower()

    def _format_dingtalk(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """格式化钉钉消息"""
        jobs = message.get('jobs', [])

        if not jobs:
            return {"msgtype": "text", "text": {"content": "暂无新职位"}}

        content = f"### InternScout - 新增 {len(jobs)} 个实习职位\n\n"
        for job in jobs[:10]:
            content += f"**{job.get('title')}** @ {job.get('company')}\n\n"
            content += f"地点: {job.get('location', '不限')} | "
            content += f"薪资: {job.get('salary', '面议')}\n\n"
            content += f"[查看详情]({job.get('url')})\n\n---\n\n"

        return {
            "msgtype": "markdown",
            "markdown": {
                "title": f"新增 {len(jobs)} 个实习职位",
                "text": content,
            }
        }

    def _format_wechat(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """格式化企业微信消息"""
        jobs = message.get('jobs', [])

        if not jobs:
            return {"msgtype": "text", "text": {"content": "暂无新职位"}}

        content = f"InternScout - 新增 {len(jobs)} 个实习职位\n\n"
        for job in jobs[:10]:
            content += f"职位: {job.get('title')}\n"
            content += f"公司: {job.get('company')}\n"
            content += f"地点: {job.get('location', '不限')}\n"
            content += f"薪资: {job.get('salary', '面议')}\n"
            content += f"链接: {job.get('url')}\n"
            content += "-" * 30 + "\n"

        return {
            "msgtype": "text",
            "text": {"content": content}
        }

    def _format_feishu(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """格式化飞书消息"""
        jobs = message.get('jobs', [])

        if not jobs:
            return {"msg_type": "text", "content": {"text": "暂无新职位"}}

        content = f"InternScout - 新增 {len(jobs)} 个实习职位\n\n"
        for job in jobs[:10]:
            content += f"**{job.get('title')}** @ {job.get('company')}\n"
            content += f"地点: {job.get('location', '不限')} | "
            content += f"薪资: {job.get('salary', '面议')}\n\n"

        return {
            "msg_type": "text",
            "content": {"text": content}
        }

    def send(self, message: Dict[str, Any]) -> bool:
        """发送Webhook通知"""
        try:
            if self.webhook_type == "dingtalk":
                payload = self._format_dingtalk(message)
            elif self.webhook_type in ["wechat", "wecom", "企业微信"]:
                payload = self._format_wechat(message)
            elif self.webhook_type in ["feishu", "lark", "飞书"]:
                payload = self._format_feishu(message)
            else:
                payload = message

            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            response.raise_for_status()

            logger.info(f"Webhook notification sent to {self.webhook_type}")
            return True

        except Exception as e:
            logger.error(f"Failed to send webhook: {e}")
            return False


class RSSNotifier(Notifier):
    """RSS订阅生成器"""

    def __init__(self, feed_title: str = "InternScout", feed_link: str = "", max_items: int = 100):
        self.feed_title = feed_title
        self.feed_link = feed_link
        self.max_items = max_items
        self.items: List[Dict[str, Any]] = []

    def add_item(self, item: Dict[str, Any]):
        """添加RSS条目"""
        self.items.append(item)
        # 保持最大数量
        if len(self.items) > self.max_items:
            self.items = self.items[-self.max_items:]

    def generate_feed(self) -> str:
        """生成RSS XML"""
        now = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0800")

        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>{self.feed_title}</title>
        <link>{self.feed_link}</link>
        <description>实习职位信息聚合</description>
        <language>zh-CN</language>
        <lastBuildDate>{now}</lastBuildDate>
"""

        for item in self.items:
            title = item.get('title', '未知职位')
            company = item.get('company', '未知公司')
            link = item.get('url', '')
            description = item.get('description', '')
            pub_date = item.get('posted_at') or item.get('created_at') or now

            xml += f"""
        <item>
            <title>{title} @ {company}</title>
            <link>{link}</link>
            <description><![CDATA[{description}]]></description>
            <pubDate>{pub_date}</pubDate>
        </item>
"""

        xml += """
    </channel>
</rss>
"""
        return xml

    def send(self, message: Any) -> bool:
        """发送消息（实际为添加条目）"""
        if isinstance(message, dict):
            self.add_item(message)
        elif isinstance(message, list):
            for item in message:
                self.add_item(item)
        return True

    def save_to_file(self, filepath: str):
        """保存RSS到文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(self.generate_feed())
        logger.info(f"RSS feed saved to {filepath}")


class NotificationManager:
    """通知管理器 - 统一管理多种通知渠道"""

    def __init__(self):
        self.notifiers: Dict[str, Notifier] = {}

    def add_notifier(self, name: str, notifier: Notifier):
        """添加通知器"""
        self.notifiers[name] = notifier

    def remove_notifier(self, name: str):
        """移除通知器"""
        if name in self.notifiers:
            del self.notifiers[name]

    def notify(self, message: Any, channels: List[str] = None) -> Dict[str, bool]:
        """
        发送通知到指定渠道

        Args:
            message: 消息内容
            channels: 指定渠道，None表示所有渠道

        Returns:
            各渠道发送结果
        """
        results = {}
        targets = channels or list(self.notifiers.keys())

        for name in targets:
            if name in self.notifiers:
                try:
                    result = self.notifiers[name].send(message)
                    results[name] = result
                except Exception as e:
                    logger.error(f"Notification to {name} failed: {e}")
                    results[name] = False

        return results

    def notify_new_jobs(self, jobs: List[Dict[str, Any]], channels: List[str] = None):
        """发送新职位通知"""
        if not jobs:
            return {}

        results = {}
        targets = channels or list(self.notifiers.keys())

        for name in targets:
            notifier = self.notifiers.get(name)
            if not notifier:
                continue

            try:
                if isinstance(notifier, EmailNotifier):
                    result = notifier.send_jobs_notification(jobs)
                elif isinstance(notifier, WebhookNotifier):
                    result = notifier.send({'jobs': jobs})
                elif isinstance(notifier, RSSNotifier):
                    result = notifier.send(jobs)
                else:
                    result = notifier.send(jobs)

                results[name] = result
            except Exception as e:
                logger.error(f"Notification to {name} failed: {e}")
                results[name] = False

        return results


def create_notifier_from_config(config: Dict[str, Any]) -> NotificationManager:
    """从配置创建通知管理器"""
    manager = NotificationManager()

    # Email通知
    email_config = config.get('email', {})
    if email_config.get('enabled'):
        notifier = EmailNotifier(
            smtp_host=email_config['smtp_host'],
            smtp_port=email_config['smtp_port'],
            smtp_user=email_config['smtp_user'],
            smtp_password=email_config['smtp_password'],
            recipients=email_config.get('recipients', []),
        )
        manager.add_notifier('email', notifier)

    # Webhook通知
    webhook_config = config.get('webhook', {})
    if webhook_config.get('enabled'):
        notifier = WebhookNotifier(
            webhook_url=webhook_config['url'],
            webhook_type=webhook_config.get('type', 'dingtalk'),
        )
        manager.add_notifier('webhook', notifier)

    # RSS订阅
    rss_config = config.get('rss', {})
    if rss_config.get('enabled'):
        notifier = RSSNotifier(
            feed_title="InternScout Jobs",
            max_items=rss_config.get('max_items', 100),
        )
        manager.add_notifier('rss', notifier)

    return manager
