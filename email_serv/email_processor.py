import os
import logging
from dotenv import load_dotenv
from mailersend import emails

# Load environment variables from .env file
load_dotenv()

# Frontend URL
FRONTEND_URL = os.environ.get('FRONTEND_URL')

logger = logging.getLogger('uvicorn.error')
logger.setLevel(logging.DEBUG)

# Load environment variables from .env file
load_dotenv()

# Environment variables
EMAIL_API_TOKEN = os.environ.get("EMAIL_API_TOKEN_TEST")
SERVICE_NAME = os.environ.get("SERVICE_NAME", "Nappio")

if not EMAIL_API_TOKEN:
    raise ValueError("SENDER_API_TOKEN is not set in the environment variables.")

def send_confirmation_email(to_email: str, first_name: str, confirmation_link: str):
    """
    Send a confirmation email to the specified recipient using MailerSend.
    """
    logger.info(f"Sending confirmation email to {to_email}")
    
    try:
        # Initialize MailerSend email client
        mailer = emails.NewEmail(EMAIL_API_TOKEN)
        
        # Define the email body
        mail_body = {}
        
        # Set sender details
        mail_from = {
            "name": SERVICE_NAME,
            #TODO: hardcoded email, should be done better
            "email": "info@nappio.co.uk"
        }
        mailer.set_mail_from(mail_from, mail_body)
        
        # Set recipient details
        recipients = [
            {
                "name": first_name,
                "email": to_email
            }
        ]
        mailer.set_mail_to(recipients, mail_body)
        
        # Set email subject
        mailer.set_subject(f"Confirm your email for {SERVICE_NAME}", mail_body)
        
        # Set email content (HTML and plain text)
        html_content = f"""
        <p>Hi {first_name},</p>
        <p>Thank you for signing up! Please confirm your email by clicking the link below:</p>
        <p><a href="{confirmation_link}">Confirm Email</a></p>
        <p>If you didn't sign up, you can ignore this email.</p>
        <p>Best,<br>The {SERVICE_NAME} Team</p>
        """
        plaintext_content = f"""
        Hi {first_name},
        
        Thank you for signing up! Please confirm your email by clicking the link below:
        {confirmation_link}
        
        If you didn't sign up, you can ignore this email.
        
        Best,
        The {SERVICE_NAME} Team
        """
        mailer.set_html_content(html_content, mail_body)
        mailer.set_plaintext_content(plaintext_content, mail_body)
        
        # Optionally, set reply-to address
        reply_to = [
            {
                "name": "Nappio Info",
                #TODO: hardcoded email, should be done better
                "email": "info@nappio.co.uk"
            }
        ]
        mailer.set_reply_to(reply_to, mail_body)
        
        # Send the email
        response = mailer.send(mail_body)
        
        # Check the response status
        #TODO: hardcoded response, should be done better
        if response.strip() != '202':
            logger.error(f"Failed to send email to {to_email}. response: {response}, response type: {type(response)}")
            return {"response": response}
        
        # Log and return the success response
        logger.info(f"Email sent successfully to {to_email}\nresponse: {response}")
        return {"status": 200, "response": response}
    
    except Exception as e:
        logger.exception(f"Failed to send email to {to_email}: {str(e)}")
        return {"status": 500, "error": str(e)}
    
def send_new_subscription_email(to_email: str, first_name: str, subscription_items: list[dict]):
    """
    Send a subscription confirmation email to the specified recipient using MailerSend.
    """
    logger.info(f"Sending subscription email to {to_email}")
    
    try:
        # Initialize MailerSend email client
        mailer = emails.NewEmail(EMAIL_API_TOKEN)
        
        # Define the email body
        mail_body = {}
        
        # Set sender details
        mail_from = {
            "name": SERVICE_NAME,
            #TODO: hardcoded email, should be done better
            "email": "info@nappio.co.uk",
        }

        mailer.set_mail_from(mail_from, mail_body)

                # Set recipient details
        recipients = [
            {
                "name": first_name,
                "email": to_email
            }
        ]
        mailer.set_mail_to(recipients, mail_body)
        
        # Set email subject
        mailer.set_subject(f"Subscription confirmation: {SERVICE_NAME}", mail_body)
        
        # Set email content (HTML and plain text)
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <p>Hi {first_name},</p>
            <p>Congratulations on starting your subscription!</p>
            
            <h3>Subscription Details:</h3>
            <table style="border-collapse: collapse; width: 100%; margin-top: 10px; margin-bottom: 20px;">
                <tr style="background-color: #f7b18a;">
                    <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Item</th>
                    <th style="border: 1px solid #ddd; padding: 8px; text-align: right;">Price</th>
                </tr>
        """
        for item in subscription_items:
            html_content += f"""
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px;">{item['item_name']}</td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{item['cost']}</td>
                </tr>"""

        html_content += f"""
            </table>

            <p>We'll be in touch to arrange your onboarding session with a member of our team.</p>
            <p>Best regards,<br>The {SERVICE_NAME} Team</p>
            <a href="{FRONTEND_URL}">Visit our website</a>
        </div>
        """

        # Plain text content
        plaintext_content = f"""
            Hi {first_name},   
            Congratulations on starting your subscription!

            Subscription Details:
            {'=' * 50}
            {' ' * 2}Item{' ' * 26}Price
            {'-' * 50}"""

        for item in subscription_items:

            plaintext_content += f"\n{item['item_name']:<30}{item['cost']:>12}"

        plaintext_content += f"""
            {'=' * 50}

            We'll be in touch to arrange your onboarding session with a member of our team

            Best regards,
            The {SERVICE_NAME} Team
            {FRONTEND_URL}
        """
        
        mailer.set_html_content(html_content, mail_body)
        mailer.set_plaintext_content(plaintext_content, mail_body)
        
        # Optionally, set reply-to address
        reply_to = [
            {
                "name": "Nappio Info",
                "email": "info@nappio.co.uk"
            }
        ]
        mailer.set_reply_to(reply_to, mail_body)
        
        # Send the email
        response = mailer.send(mail_body)
        
        # Check the response status
        #TODO: hardcoded response, should be done better
        if response.strip() != '202':
            logger.error(f"Failed to send email to {to_email}. response: {response}, response type: {type(response)}")
            return {"response": response}
        
        # Log and return the success response
        logger.info(f"Email sent successfully to {to_email}\nresponse: {response}")
        return {"status": 200, "response": response}
    
    except Exception as e:
        logger.exception(f"Failed to send email to {to_email}: {str(e)}")
        return {"status": 500, "error": str(e)}
    

def send_order_email_to_team(subject: str, customer_email: str, customer_name: str, items: list[dict]):
    """
    Send an email to the internal team using MailerSend.
    """
    try:
        logger.info(f"Sending email to team with subject: {subject}")

        #TODO: Move this to .env
        team_email = "info@nappio.co.uk"
        mailer = emails.NewEmail(EMAIL_API_TOKEN)
        mail_body = {}
        mail_from = {
            "name": SERVICE_NAME,
            "email": "info@nappio.co.uk",
        }
        mailer.set_mail_from(mail_from, mail_body)
        recipients = [
            {
                "name": "Nappio Team",
                "email": team_email
            }
        ]
        mailer.set_mail_to(recipients, mail_body)
        mailer.set_subject(subject, mail_body)

        # HTML Content
        html_content = f"""
        <h2>New Order Received</h2>

        <p><strong>Customer:</strong> {customer_name}<br>
        <strong>Email:</strong> {customer_email}</p>

        <h3>Items:</h3>
        <table style="border-collapse: collapse; width: 100%; margin-top: 10px;">
            <tr style="background-color: #f7b18a;">
                <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Item</th>
                <th style="border: 1px solid #ddd; padding: 8px; text-align: right;">Quantity</th>
                <th style="border: 1px solid #ddd; padding: 8px; text-align: right;">Item Cost</th>

            </tr>
        """
        total_cost = 0
        for item in items:

            html_content += f"""
            <tr>
                <td style="border: 1px solid #ddd; padding: 8px;">{item['item_name']}</td>
                <td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{item['quantity']}</td>
                <td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{item['cost']}</td>
            </tr>"""

        html_content += f"</table>"

        # Plain text content
        plaintext_content = f"""
            New Order Received

            Customer: {customer_name}
            Email: {customer_email}

            Items:
            {'=' * 80}
            {' ' * 2}Item{' ' * 26}Quantity{' ' * 5}Cost{' ' * 7}
        """

        for item in items:
            plaintext_content += f"\n{item['item_name']:<30}{item['quantity']:>8}{item['cost']:>12}"

        mailer.set_html_content(html_content, mail_body)
        mailer.set_plaintext_content(plaintext_content, mail_body)

        response = mailer.send(mail_body)
        if response.strip() != '202':
            logger.error(f"Failed to send email to {team_email}. response: {response}, response type: {type(response)}")
            return {"response": response}
        logger.info(f"Email sent successfully to {team_email}\nresponse: {response}")
        return {"status": 200, "response": response}
    except Exception as e:
        logger.exception(f"Failed to send email to {team_email}: {str(e)}")
        return {"status": 500, "error": str(e)}