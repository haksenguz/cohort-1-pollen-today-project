"""Web push delivery for stored alerts.

`send_push` fans one message out to every push subscription a user has. It
never raises: a push is a convenience on top of an alert that is already in the
database, so any failure is logged and swallowed. With no VAPID keys configured
it does nothing at all.
"""

import asyncio
import json
import logging

from pywebpush import WebPushException, webpush
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import delete, select

from app.core.config import get_settings
from app.models import PushSubscription

logger = logging.getLogger(__name__)

# The push service answers 404 or 410 when the browser has unsubscribed or the
# endpoint has expired. Such a subscription can never receive again, so it goes.
_GONE_STATUSES = (404, 410)


async def send_push(
    session: AsyncSession,
    user_id: int,
    title: str,
    body: str,
    url: str = "/alerts",
) -> None:
    settings = get_settings()
    if not settings.vapid_public_key or not settings.vapid_private_key:
        return

    try:
        result = await session.execute(
            select(PushSubscription).where(PushSubscription.user_id == user_id)
        )
        subscriptions = list(result.scalars().all())
        if not subscriptions:
            return

        payload = json.dumps({"title": title, "body": body, "url": url})
        claims = {"sub": settings.vapid_subject or "mailto:ismoiljonedu@gmail.com"}
        gone: list[str] = []

        for sub in subscriptions:
            info = {"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}}
            try:
                await asyncio.to_thread(
                    webpush,
                    subscription_info=info,
                    data=payload,
                    vapid_private_key=settings.vapid_private_key,
                    vapid_claims=dict(claims),
                )
            except WebPushException as exc:
                status = getattr(exc.response, "status_code", None)
                if status in _GONE_STATUSES:
                    gone.append(sub.endpoint)
                else:
                    logger.warning("web push to subscription %s failed: %s", sub.id, exc)
            except Exception:
                logger.warning("web push to subscription %s failed", sub.id, exc_info=True)

        if gone:
            await session.execute(
                delete(PushSubscription).where(PushSubscription.endpoint.in_(gone))
            )
            await session.commit()
    except Exception:
        logger.warning("web push for user %s failed", user_id, exc_info=True)
