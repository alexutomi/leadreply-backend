import os
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
FROM_EMAIL       = os.environ.get("FROM_EMAIL", "support@leadreplygroup.com")
DASHBOARD_URL    = "https://leadreplygroup.com/login.html"


def send_business_welcome(first_name: str, email: str, twilio_number: str, plan: str):
    subject = "Welcome to LeadReply — Your Account is Ready!"

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; background:#f8fafc; margin:0; padding:0; }}
  .wrapper {{ max-width:580px; margin:40px auto; background:white; border-radius:16px; overflow:hidden; box-shadow:0 4px 20px rgba(0,0,0,0.08); }}
  .header {{ background:#2563eb; padding:36px 40px; text-align:center; }}
  .header h1 {{ color:white; font-size:24px; margin:0; font-weight:700; }}
  .header p {{ color:rgba(255,255,255,0.8); font-size:14px; margin:8px 0 0; }}
  .body {{ padding:40px; }}
  .greeting {{ font-size:18px; font-weight:700; color:#0f172a; margin-bottom:12px; }}
  .text {{ font-size:15px; color:#475569; line-height:1.7; margin-bottom:20px; }}
  .number-box {{ background:#eff6ff; border:1px solid #bfdbfe; border-radius:12px; padding:20px 24px; margin:24px 0; text-align:center; }}
  .number-label {{ font-size:12px; font-weight:700; color:#2563eb; text-transform:uppercase; letter-spacing:.08em; margin-bottom:8px; }}
  .number {{ font-size:32px; font-weight:700; color:#1e293b; letter-spacing:2px; font-family:monospace; }}
  .steps {{ background:#f8fafc; border-radius:12px; padding:24px; margin:24px 0; }}
  .steps h3 {{ font-size:15px; font-weight:700; color:#0f172a; margin:0 0 16px; }}
  .step {{ margin-bottom:14px; padding-left:36px; position:relative; }}
  .step-num {{ position:absolute; left:0; top:0; width:24px; height:24px; background:#2563eb; color:white; border-radius:50%; font-size:12px; font-weight:700; text-align:center; line-height:24px; }}
  .step-text {{ font-size:14px; color:#475569; line-height:1.6; }}
  .btn {{ display:block; background:#2563eb; color:white; text-align:center; padding:16px 32px; border-radius:10px; text-decoration:none; font-size:16px; font-weight:700; margin:28px 0; }}
  .login-box {{ background:#f1f5f9; border-radius:10px; padding:16px 20px; margin:20px 0; }}
  .login-label {{ font-size:12px; font-weight:700; color:#64748b; text-transform:uppercase; letter-spacing:.06em; margin-bottom:4px; }}
  .login-value {{ font-size:15px; color:#0f172a; font-weight:600; }}
  .footer {{ background:#f8fafc; padding:24px 40px; text-align:center; border-top:1px solid #e2e8f0; }}
  .footer p {{ font-size:12px; color:#94a3b8; margin:4px 0; line-height:1.6; }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>Welcome to LeadReply!</h1>
    <p>Your missed call automation is ready to go</p>
  </div>
  <div class="body">
    <div class="greeting">Hi {first_name}!</div>
    <p class="text">Your LeadReply account has been created and your dedicated phone number is ready. From now on every customer who calls and does not get an answer will automatically receive a personalized text reply.</p>

    <div class="number-box">
      <div class="number-label">Your LeadReply Number</div>
      <div class="number">{twilio_number if twilio_number and twilio_number != '+15550000000' else 'Check your dashboard'}</div>
    </div>

    <div class="login-box">
      <div class="login-label">Your Login Email</div>
      <div class="login-value">{email}</div>
    </div>

    <a href="{DASHBOARD_URL}" class="btn">Access My Dashboard</a>

    <div class="steps">
      <h3>Your Next Steps</h3>
      <div class="step">
        <div class="step-num">1</div>
        <div class="step-text"><strong>Log into your dashboard</strong> using the button above and the email you signed up with.</div>
      </div>
      <div class="step">
        <div class="step-num">2</div>
        <div class="step-text"><strong>Complete your AI profile</strong> so your replies sound like your real team.</div>
      </div>
      <div class="step">
        <div class="step-num">3</div>
        <div class="step-text"><strong>Share your LeadReply number</strong> with customers or forward your existing number to it.</div>
      </div>
      <div class="step">
        <div class="step-num">4</div>
        <div class="step-text"><strong>Watch the leads come in</strong> — every missed call gets an instant AI reply automatically.</div>
      </div>
    </div>

    <p class="text">Questions? Email us at <a href="mailto:support@leadreplygroup.com" style="color:#2563eb;">support@leadreplygroup.com</a> and we will get back to you quickly.</p>
  </div>
  <div class="footer">
    <p>2026 LeadReply Group · Houston, TX 77056</p>
    <p>You are receiving this because you signed up for LeadReply.</p>
  </div>
</div>
</body>
</html>
"""
    return _send_email(email, subject, html_content)


def send_agency_welcome(first_name: str, email: str, plan: str):
    plan_labels = {
        "agency_starter": "Agency Starter — up to 3 clients",
        "agency_growth":  "Agency Growth — up to 10 clients",
        "agency_pro":     "Agency Pro — unlimited clients"
    }
    plan_label = plan_labels.get(plan, plan)
    subject = "Your LeadReply Agency Account is Ready!"

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; background:#f8fafc; margin:0; padding:0; }}
  .wrapper {{ max-width:580px; margin:40px auto; background:white; border-radius:16px; overflow:hidden; box-shadow:0 4px 20px rgba(0,0,0,0.08); }}
  .header {{ background:#6366f1; padding:36px 40px; text-align:center; }}
  .header h1 {{ color:white; font-size:24px; margin:0; font-weight:700; }}
  .header p {{ color:rgba(255,255,255,0.8); font-size:14px; margin:8px 0 0; }}
  .body {{ padding:40px; }}
  .greeting {{ font-size:18px; font-weight:700; color:#0f172a; margin-bottom:12px; }}
  .text {{ font-size:15px; color:#475569; line-height:1.7; margin-bottom:20px; }}
  .plan-box {{ background:#eef2ff; border:1px solid #c7d2fe; border-radius:12px; padding:20px 24px; margin:24px 0; }}
  .plan-label {{ font-size:12px; font-weight:700; color:#6366f1; text-transform:uppercase; letter-spacing:.08em; margin-bottom:6px; }}
  .plan-name {{ font-size:20px; font-weight:700; color:#1e293b; }}
  .login-box {{ background:#f1f5f9; border-radius:10px; padding:16px 20px; margin:20px 0; }}
  .login-label {{ font-size:12px; font-weight:700; color:#64748b; text-transform:uppercase; letter-spacing:.06em; margin-bottom:4px; }}
  .login-value {{ font-size:15px; color:#0f172a; font-weight:600; }}
  .steps {{ background:#f8fafc; border-radius:12px; padding:24px; margin:24px 0; }}
  .steps h3 {{ font-size:15px; font-weight:700; color:#0f172a; margin:0 0 16px; }}
  .step {{ margin-bottom:14px; padding-left:36px; position:relative; }}
  .step-num {{ position:absolute; left:0; top:0; width:24px; height:24px; background:#6366f1; color:white; border-radius:50%; font-size:12px; font-weight:700; text-align:center; line-height:24px; }}
  .step-text {{ font-size:14px; color:#475569; line-height:1.6; }}
  .btn {{ display:block; background:#6366f1; color:white; text-align:center; padding:16px 32px; border-radius:10px; text-decoration:none; font-size:16px; font-weight:700; margin:28px 0; }}
  .footer {{ background:#f8fafc; padding:24px 40px; text-align:center; border-top:1px solid #e2e8f0; }}
  .footer p {{ font-size:12px; color:#94a3b8; margin:4px 0; line-height:1.6; }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>Agency Account Ready!</h1>
    <p>Start adding clients and generating recurring revenue</p>
  </div>
  <div class="body">
    <div class="greeting">Hi {first_name}!</div>
    <p class="text">Your LeadReply agency account is fully set up. You can now add clients, provision dedicated phone numbers for each one, and manage all their missed call automation from a single dashboard.</p>

    <div class="plan-box">
      <div class="plan-label">Your Plan</div>
      <div class="plan-name">{plan_label}</div>
    </div>

    <div class="login-box">
      <div class="login-label">Your Login Email</div>
      <div class="login-value">{email}</div>
    </div>

    <a href="{DASHBOARD_URL}" class="btn">Go to Agency Dashboard</a>

    <div class="steps">
      <h3>Getting Started</h3>
      <div class="step">
        <div class="step-num">1</div>
        <div class="step-text"><strong>Log into your agency dashboard</strong> using the button above.</div>
      </div>
      <div class="step">
        <div class="step-num">2</div>
        <div class="step-text"><strong>Click Add Client</strong> to provision your first client with a dedicated number.</div>
      </div>
      <div class="step">
        <div class="step-num">3</div>
        <div class="step-text"><strong>Share the number with your client</strong> and they are ready to capture missed call leads immediately.</div>
      </div>
      <div class="step">
        <div class="step-num">4</div>
        <div class="step-text"><strong>Bill your clients</strong> — most agencies charge $150-300 per month per client for this service.</div>
      </div>
    </div>

    <p class="text">Questions? Email us at <a href="mailto:support@leadreplygroup.com" style="color:#6366f1;">support@leadreplygroup.com</a>.</p>
  </div>
  <div class="footer">
    <p>2026 LeadReply Group · Houston, TX 77056</p>
    <p>You are receiving this because you signed up for a LeadReply agency account.</p>
  </div>
</div>
</body>
</html>
"""
    return _send_email(email, subject, html_content)


def _send_email(to_email: str, subject: str, html_content: str):
    try:
        sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
        message = Mail(
            from_email=Email(FROM_EMAIL, "LeadReply"),
            to_emails=To(to_email),
            subject=subject,
            html_content=Content("text/html", html_content)
        )
        response = sg.client.mail.send.post(request_body=message.get())
        print(f"✅ Email sent to {to_email} — Status: {response.status_code}")
        return True
    except Exception as e:
        print(f"❌ Email error: {e}")
        return False
