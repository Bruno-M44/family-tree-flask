#! /usr/bin/env python
"""Email sending via Resend."""

import logging

import resend
from resend.exceptions import ResendError
from flask import current_app


def send_verification_email(to_email: str, token: str) -> None:
    api_key = current_app.config.get('RESEND_API_KEY')
    frontend_url = current_app.config.get('FRONTEND_URL', 'http://localhost:5173')
    verify_url = f"{frontend_url}/verify?token={token}"

    if not api_key:
        logging.warning("[DEV] Verification email not sent. Link: %s", verify_url)
        return

    resend.api_key = api_key
    try:
        resend.Emails.send({
            "from": "noreply@family-tree.io",
            "to": to_email,
            "subject": "Vérifiez votre adresse email",
            "html": (
                "<p>Merci pour votre inscription.</p>"
                f'<p><a href="{verify_url}">Cliquez ici pour vérifier votre adresse email</a></p>'
                "<p>Ce lien est valable 24h.</p>"
            ),
        })
    except ResendError as e:
        logging.error("Failed to send verification email to %s: %s", to_email, e)
