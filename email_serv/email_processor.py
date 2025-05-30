import os
import logging
from dotenv import load_dotenv
from mailersend import emails

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
    
def send_new_subscription_email(to_email: str, first_name: str, subscription_details: dict):
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
        <p>Hi {first_name},</p>
        <p>Congratulations on starting your subscription!</p>
        <p><table><tr><td>Plan:</td><td>{subscription_details['plan_name']}</td></tr>
        <tr><td>Cost (monthly):</td><td>{subscription_details['price']}</td></tr>
        </table></p>
        <p>Best,<br>The {SERVICE_NAME} Team</p>
        """
        plaintext_content = f"""
        Hi {first_name},   
        Congratulations on starting your subscription!
        Plan: {subscription_details['plan_name']}
        Cost (monthly): {subscription_details['price']}
        Best,
        The {SERVICE_NAME} Team
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