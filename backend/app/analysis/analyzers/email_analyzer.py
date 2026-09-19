from typing import Any, Dict, List, Optional
import email
from email import policy
import os
import re
import tempfile
from datetime import datetime, timezone
import pytsk3

from app.analysis.base import BaseAnalyzer


class EmailAnalyzer(BaseAnalyzer):
    """
    Parses email artifacts from disk images:
    - .eml (RFC 822 / MIME format, e.g. Windows Live Mail, Thunderbird, Apple Mail)
    - .msg (Outlook MSG binary files)
    - .pst / .ost (Outlook Personal Storage Tables)
    """

    name = "email_analyzer"
    description = "Parses .eml, .msg, and .pst/.ost email artifacts"

    def analyze(self, target: str = None, **kwargs) -> Dict[str, Any]:
        img_info = kwargs.get("img_info")
        offset = kwargs.get("offset", 0)
        candidate_files = kwargs.get("email_files", [])

        result = {
            "parsed_emails": [],
            "total_emails_parsed": 0,
            "total_attachments_found": 0,
            "errors": [],
            "skipped": [],
        }

        if not img_info or not candidate_files:
            return result

        try:
            fs = pytsk3.FS_Info(img_info, offset=offset)
        except Exception as e:
            result["errors"].append(f"Failed to open filesystem: {e}")
            return result

        for item in candidate_files:
            path = item.get("path", "")
            name = item.get("name", "").lower()
            size = item.get("size", 0)

            if size == 0:
                result["skipped"].append(path)
                continue

            try:
                if name.endswith(".eml"):
                    parsed = self._parse_eml(fs, path, size)
                    if parsed:
                        result["parsed_emails"].append(parsed)
                        result["total_emails_parsed"] += 1
                        result["total_attachments_found"] += len(parsed.get("attachments", []))

                elif name.endswith(".msg"):
                    parsed = self._parse_msg(fs, path, size)
                    if parsed:
                        result["parsed_emails"].append(parsed)
                        result["total_emails_parsed"] += 1
                        result["total_attachments_found"] += len(parsed.get("attachments", []))

                elif name.endswith((".pst", ".ost")):
                    parsed = self._parse_pst(fs, path, size)
                    if parsed:
                        if isinstance(parsed, list):
                            result["parsed_emails"].extend(parsed)
                            result["total_emails_parsed"] += len(parsed)
                        else:
                            result["parsed_emails"].append(parsed)
                            result["total_emails_parsed"] += 1

                else:
                    result["skipped"].append(path)

            except Exception as e:
                result["errors"].append(f"{path}: {str(e)}")

        return result

    def _parse_eml(self, fs, path_in_image: str, size: int) -> Optional[Dict[str, Any]]:
        """Parse RFC 822 .eml message file."""
        tsk_path = path_in_image.replace("\\", "/")
        if not tsk_path.startswith("/"):
            tsk_path = "/" + tsk_path

        try:
            file_obj = fs.open(path=tsk_path)
            data = file_obj.read_random(0, min(size, 20 * 1024 * 1024))
        except Exception:
            return None

        try:
            msg = email.message_from_bytes(data, policy=policy.default)
        except Exception:
            try:
                msg = email.message_from_bytes(data)
            except Exception:
                return None

        subject = str(msg.get("Subject", "") or "").strip()
        sender = str(msg.get("From", "") or "").strip()
        recipient = str(msg.get("To", "") or "").strip()
        cc = str(msg.get("Cc", "") or "").strip()
        date_str = str(msg.get("Date", "") or "").strip()
        msg_id = str(msg.get("Message-ID", "") or "").strip()

        body_plain = ""
        body_html = ""
        attachments = []

        try:
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition", ""))
                    filename = part.get_filename()

                    if filename or "attachment" in content_disposition.lower():
                        att_bytes = part.get_payload(decode=True) or b""
                        attachments.append({
                            "filename": filename or "attachment.bin",
                            "content_type": content_type,
                            "size": len(att_bytes),
                        })
                    elif content_type == "text/plain" and not body_plain:
                        try:
                            body_plain = part.get_content()
                        except Exception:
                            payload = part.get_payload(decode=True)
                            if isinstance(payload, bytes):
                                body_plain = payload.decode("utf-8", errors="ignore")
                    elif content_type == "text/html" and not body_html:
                        try:
                            body_html = part.get_content()
                        except Exception:
                            payload = part.get_payload(decode=True)
                            if isinstance(payload, bytes):
                                body_html = payload.decode("utf-8", errors="ignore")
            else:
                content_type = msg.get_content_type()
                try:
                    body = msg.get_content()
                except Exception:
                    payload = msg.get_payload(decode=True)
                    body = payload.decode("utf-8", errors="ignore") if isinstance(payload, bytes) else str(payload)

                if content_type == "text/html":
                    body_html = body
                else:
                    body_plain = body

        except Exception:
            pass

        body = (body_plain or body_html or "").strip()
        snippet = body[:300].replace("\r\n", " ").replace("\n", " ")

        return {
            "source_path": path_in_image,
            "format": "EML",
            "subject": subject,
            "from": sender,
            "to": recipient,
            "cc": cc,
            "date": date_str,
            "message_id": msg_id,
            "body_snippet": snippet,
            "has_attachments": len(attachments) > 0,
            "attachments": attachments,
            "size": size,
        }

    def _parse_msg(self, fs, path_in_image: str, size: int) -> Optional[Dict[str, Any]]:
        """Parse Outlook .msg format using extract_msg or fallback."""
        try:
            import extract_msg
        except ImportError:
            return self._parse_msg_fallback(fs, path_in_image, size)

        tsk_path = path_in_image.replace("\\", "/")
        if not tsk_path.startswith("/"):
            tsk_path = "/" + tsk_path

        try:
            file_obj = fs.open(path=tsk_path)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".msg")
            tmp_path = tmp.name
            tmp.close()

            with open(tmp_path, "wb") as out:
                out.write(file_obj.read_random(0, min(size, 50 * 1024 * 1024)))

            try:
                msg = extract_msg.Message(tmp_path)
                attachments = [
                    {
                        "filename": att.longFilename or att.shortFilename or "attachment.bin",
                        "size": len(att.data) if att.data else 0,
                    }
                    for att in msg.attachments
                ]
                res = {
                    "source_path": path_in_image,
                    "format": "MSG",
                    "subject": msg.subject or "",
                    "from": msg.sender or "",
                    "to": msg.to or "",
                    "date": str(msg.date) if msg.date else "",
                    "body_snippet": (msg.body or "")[:300].replace("\r\n", " ").replace("\n", " "),
                    "has_attachments": len(attachments) > 0,
                    "attachments": attachments,
                    "size": size,
                }
                msg.close()
                return res
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        except Exception as e:
            return {
                "source_path": path_in_image,
                "format": "MSG",
                "error": f"Failed to parse MSG: {e}",
                "size": size,
            }

    def _parse_msg_fallback(self, fs, path_in_image: str, size: int) -> Optional[Dict[str, Any]]:
        """Fallback header extraction for MSG files if extract_msg is not installed."""
        tsk_path = path_in_image.replace("\\", "/")
        if not tsk_path.startswith("/"):
            tsk_path = "/" + tsk_path

        try:
            file_obj = fs.open(path=tsk_path)
            data = file_obj.read_random(0, min(size, 2 * 1024 * 1024))
            text = data.decode("latin-1", errors="ignore")

            subject = ""
            m_sub = re.search(r"Subject:\s*(.+)", text, re.IGNORECASE)
            if m_sub:
                subject = m_sub.group(1).strip()

            from_addr = ""
            m_from = re.search(r"From:\s*(.+)", text, re.IGNORECASE)
            if m_from:
                from_addr = m_from.group(1).strip()

            to_addr = ""
            m_to = re.search(r"To:\s*(.+)", text, re.IGNORECASE)
            if m_to:
                to_addr = m_to.group(1).strip()

            date_str = ""
            m_date = re.search(r"Date:\s*(.+)", text, re.IGNORECASE)
            if m_date:
                date_str = m_date.group(1).strip()

            return {
                "source_path": path_in_image,
                "format": "MSG (raw fallback)",
                "subject": subject,
                "from": from_addr,
                "to": to_addr,
                "date": date_str,
                "body_snippet": "Install 'extract_msg' (pip install extract_msg) for full MSG body parsing",
                "has_attachments": False,
                "attachments": [],
                "size": size,
            }
        except Exception:
            return None

    def _parse_pst(self, fs, path_in_image: str, size: int) -> Optional[Dict[str, Any]]:
        """Identify PST/OST Outlook database files."""
        tsk_path = path_in_image.replace("\\", "/")
        if not tsk_path.startswith("/"):
            tsk_path = "/" + tsk_path

        try:
            file_obj = fs.open(path=tsk_path)
            header = file_obj.read_random(0, 512)
            is_valid_pst = header.startswith(b"!BDN")
        except Exception:
            is_valid_pst = False

        return {
            "source_path": path_in_image,
            "format": "PST/OST",
            "subject": f"Outlook Storage File ({'Valid !BDN Header' if is_valid_pst else 'Unknown Header'})",
            "from": "",
            "to": "",
            "date": "",
            "body_snippet": f"PST/OST archive detected ({size:,} bytes). Install 'pypff' for item-level PST extraction.",
            "has_attachments": False,
            "attachments": [],
            "size": size,
        }
