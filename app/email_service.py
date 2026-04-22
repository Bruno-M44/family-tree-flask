#! /usr/bin/env python
"""Email sending via Resend."""

import logging

import resend
from resend.exceptions import ResendError
from flask import current_app

_LOGO_SVG = """
<svg version="1.0" xmlns="http://www.w3.org/2000/svg" height="56" viewBox="0 0 159.000000 179.000000"
     preserveAspectRatio="xMidYMid meet" style="display:block;margin:0 auto 12px;">
  <g transform="translate(0.000000,179.000000) scale(0.100000,-0.100000)" fill="#0cabf0" stroke="none">
    <path d="M685 1520 c-8 -13 51 -270 77 -329 17 -41 18 -54 7 -163 -11 -111
-18 -133 -35 -107 -3 6 -26 20 -49 30 -53 23 -54 29 -47 204 4 121 3 135 -12
141 -30 12 -40 -14 -44 -114 -2 -53 -8 -101 -12 -105 -4 -5 -35 14 -68 42 -64
54 -88 62 -99 34 -8 -21 84 -108 138 -130 29 -11 39 -21 39 -37 0 -38 -35 -46
-149 -34 -107 12 -131 6 -131 -32 0 -28 25 -41 95 -50 37 -5 69 -10 71 -13 2
-2 -8 -25 -22 -51 -24 -43 -25 -49 -11 -63 21 -21 38 -8 74 59 48 89 124 99
201 27 l42 -40 0 -280 c0 -174 4 -288 10 -300 12 -21 50 -25 68 -7 9 9 12 78
12 249 l0 237 31 6 c53 10 71 7 105 -19 18 -14 40 -25 49 -25 24 0 30 28 10
50 -22 24 -22 24 40 39 60 15 75 26 75 57 0 43 -27 45 -146 13 -60 -16 -121
-29 -136 -29 -26 0 -28 3 -28 43 l0 42 61 24 c34 13 87 46 122 76 l62 52 89
-34 c95 -36 119 -36 114 -2 -2 17 -21 28 -81 51 l-77 30 47 42 c39 36 45 46
40 68 -8 30 -31 42 -55 29 -9 -5 -66 -54 -127 -110 -60 -55 -127 -107 -149
-115 l-39 -15 7 52 c3 28 6 66 6 83 0 30 5 33 94 73 107 49 153 83 181 135 18
34 19 37 2 53 -16 17 -19 16 -55 -23 -30 -34 -125 -94 -147 -94 -3 0 -5 42 -5
93 0 99 -7 121 -36 115 -17 -3 -20 -16 -24 -112 -5 -110 -14 -132 -40 -101 -7
8 -31 77 -54 152 -36 115 -46 139 -63 141 -12 2 -24 -2 -28 -8z"/>
  </g>
</svg>
"""

_BASE_STYLE = """
<style>
  body { margin: 0; padding: 0; background-color: #e8edf5; font-family: Arial, sans-serif; }
  .wrapper { width: 100%; padding: 40px 0; background-color: #e8edf5; }
  .card { max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 12px;
          overflow: hidden; box-shadow: 0 4px 24px rgba(0,18,87,0.12); }
  .header { background-color: #001257; padding: 36px 40px 28px; text-align: center; }
  .header h1 { margin: 0; color: #ffffff; font-size: 20px; font-weight: 700; letter-spacing: 0.5px; }
  .header p { margin: 6px 0 0; color: rgba(255,255,255,0.7); font-size: 13px; }
  .body { padding: 36px 40px; }
  .body p { margin: 0 0 16px; color: #374151; font-size: 15px; line-height: 1.6; }
  .highlight { background: #e6f7fe; border-left: 4px solid #0cabf0;
               border-radius: 6px; padding: 14px 18px; margin: 20px 0; }
  .highlight strong { color: #001257; font-size: 16px; }
  .btn-wrap { text-align: center; margin: 28px 0 8px; }
  .btn { display: inline-block; padding: 14px 36px; background-color: #0cabf0;
         color: #ffffff !important; text-decoration: none; border-radius: 8px;
         font-size: 15px; font-weight: 700; letter-spacing: 0.3px; }
  .footer { padding: 20px 40px; text-align: center; border-top: 1px solid #e5e7eb; }
  .footer p { margin: 0; color: #9ca3af; font-size: 12px; }
</style>
"""


def _build_html(header_title: str, header_subtitle: str, body: str, btn_label: str, btn_url: str) -> str:
    """Assemble a full HTML email from header, body block, and a CTA button."""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8">{_BASE_STYLE}</head>
<body>
  <div class="wrapper">
    <div class="card">
      <div class="header">
        {_LOGO_SVG}
        <h1>{header_title}</h1>
        <p>{header_subtitle}</p>
      </div>
      <div class="body">
        {body}
        <div class="btn-wrap">
          <a href="{btn_url}" class="btn">{btn_label}</a>
        </div>
      </div>
      <div class="footer">
        <p>Vous recevez cet email car quelqu'un vous a ajouté à un arbre généalogique.</p>
      </div>
    </div>
  </div>
</body>
</html>"""


def _send(to_email: str, subject: str, html: str, log_fallback: str) -> None:
    """Send an email via Resend or log the fallback URL in dev mode."""
    api_key: str = current_app.config.get('RESEND_API_KEY')
    if not api_key:
        logging.warning("[DEV] Email not sent to %s. %s", to_email, log_fallback)
        return
    resend.api_key = api_key
    try:
        resend.Emails.send({
            "from": "noreply@family-tree.io",
            "to": to_email,
            "subject": subject,
            "html": html,
        })
    except ResendError as err:
        logging.error("Failed to send email to %s: %s", to_email, err)


def send_verification_email(to_email: str, token: str) -> None:
    """Send an email verification link to a newly registered or updated user."""
    frontend_url: str = current_app.config.get('FRONTEND_URL', 'http://localhost:5173')
    verify_url: str = f"{frontend_url}/verify?token={token}"

    body = """
        <p>Merci pour votre inscription sur <strong>Family Tree</strong> !</p>
        <p>Pour activer votre compte, cliquez sur le bouton ci-dessous.
           Ce lien est valable <strong>24 heures</strong>.</p>
    """
    html = _build_html(
        header_title="Vérifiez votre adresse email",
        header_subtitle="Une dernière étape avant de commencer",
        body=body,
        btn_label="Vérifier mon adresse email",
        btn_url=verify_url,
    )
    _send(to_email, "Vérifiez votre adresse email – Family Tree", html,
          f"Verify link: {verify_url}")


def send_member_added_email(
    to_email: str,
    tree_title: str,
    family_name: str,
    inviter_name: str,
) -> None:
    """Notify an existing user that they have been added to a family tree."""
    frontend_url: str = current_app.config.get('FRONTEND_URL', 'http://localhost:5173')

    body = f"""
        <p>Bonjour,</p>
        <p><strong>{inviter_name}</strong> vous a ajouté à son arbre généalogique :</p>
        <div class="highlight">
          <strong>🌳 {tree_title}</strong><br>
          <span style="color:#6b7280; font-size:14px;">Famille {family_name}</span>
        </div>
        <p>Connectez-vous à votre compte pour le consulter et découvrir l'histoire de cette famille.</p>
    """
    html = _build_html(
        header_title="Vous avez accès à un arbre généalogique",
        header_subtitle=f"Invitation de {inviter_name}",
        body=body,
        btn_label="Voir l'arbre généalogique",
        btn_url=frontend_url,
    )
    _send(to_email, f"Vous avez été ajouté à l'arbre « {tree_title} »", html,
          f"Member added to tree '{tree_title}'")


def send_member_invitation_email(
    to_email: str,
    tree_title: str,
    family_name: str,
    inviter_name: str,
    invitation_token: str,
) -> None:
    """Invite a person without an account to register and automatically join a family tree."""
    frontend_url: str = current_app.config.get('FRONTEND_URL', 'http://localhost:5173')
    register_url: str = f"{frontend_url}/register?invitation_token={invitation_token}"

    body = f"""
        <p>Bonjour,</p>
        <p><strong>{inviter_name}</strong> vous invite à rejoindre son arbre généalogique :</p>
        <div class="highlight">
          <strong>🌳 {tree_title}</strong><br>
          <span style="color:#6b7280; font-size:14px;">Famille {family_name}</span>
        </div>
        <p>Pour accéder à cet arbre, créez votre compte gratuitement avec cette adresse email.
           Vous serez automatiquement ajouté à l'arbre dès votre inscription.</p>
        <p style="color:#6b7280; font-size:13px;">⏳ Ce lien est valable 7 jours.</p>
    """
    html = _build_html(
        header_title="Vous êtes invité !",
        header_subtitle=f"Invitation de {inviter_name}",
        body=body,
        btn_label="Créer mon compte",
        btn_url=register_url,
    )
    _send(to_email, f"Invitation à rejoindre l'arbre généalogique « {tree_title} »", html,
          f"Invitation link: {register_url}")
