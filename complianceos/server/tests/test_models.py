"""ORM model tests — CRUD, constraints, relationships, and type correctness.

Every model is tested for:
  - Happy-path creation and query-back
  - Unique constraints (duplicate key raises IntegrityError)
  - CHECK constraints (invalid enum / range raises IntegrityError)
  - Cascade deletes where defined
  - Correct Python type for date vs datetime columns
"""

import uuid
from datetime import date, datetime

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from models.ca_client_link import CAClientLink
from models.ca_profile import CAProfile
from models.compliance_item import ClientComplianceItem, ComplianceItem
from models.document import Document
from models.health_score import HealthScore
from models.invoice import Invoice
from models.message import Message
from models.notification import Notification
from models.payment import Payment
from models.regulation import Regulation
from models.smb_profile import SMBProfile
from models.task import Task
from models.user import User


# ---------------------------------------------------------------------------
# Factory helpers — minimal valid objects
# ---------------------------------------------------------------------------

async def _user(db, mobile: str, role: str = "ca") -> User:
    u = User(mobile=mobile, role=role, full_name="Test User")
    db.add(u)
    await db.flush()
    return u


async def _ca(db, user: User) -> CAProfile:
    p = CAProfile(user_id=user.id)
    db.add(p)
    await db.flush()
    return p


async def _smb(db, user: User) -> SMBProfile:
    p = SMBProfile(user_id=user.id, company_name="Test Co")
    db.add(p)
    await db.flush()
    return p


async def _link(db, ca: CAProfile, smb: SMBProfile, status: str = "active") -> CAClientLink:
    lnk = CAClientLink(ca_id=ca.id, client_id=smb.id, status=status)
    db.add(lnk)
    await db.flush()
    return lnk


async def _compliance_item(db, item_id: str = "GST_MONTHLY_3B") -> ComplianceItem:
    ci = ComplianceItem(
        id=item_id,
        name="GST Monthly GSTR-3B",
        compliance_type="gst",
    )
    db.add(ci)
    await db.flush()
    return ci


async def _client_compliance(
    db, smb: SMBProfile, ca: CAProfile, item: ComplianceItem
) -> ClientComplianceItem:
    cci = ClientComplianceItem(
        client_id=smb.id,
        ca_id=ca.id,
        compliance_item_id=item.id,
        financial_year="2025-26",
        due_date=date(2025, 7, 20),
    )
    db.add(cci)
    await db.flush()
    return cci


async def _task(db, ca: CAProfile, smb: SMBProfile) -> Task:
    t = Task(
        ca_id=ca.id,
        client_id=smb.id,
        title="Collect bank statements",
        assigned_to="client",
        status="pending",
        created_by="ca",
    )
    db.add(t)
    await db.flush()
    return t


async def _document(db, smb: SMBProfile, ca: CAProfile | None = None) -> Document:
    d = Document(
        client_id=smb.id,
        ca_id=ca.id if ca else None,
        file_name="bank_statement.pdf",
        file_size_bytes=512000,
        mime_type="application/pdf",
        r2_key=f"docs/{uuid.uuid4()}.pdf",
        uploaded_by="client",
    )
    db.add(d)
    await db.flush()
    return d


async def _message(db, ca: CAProfile, smb: SMBProfile) -> Message:
    m = Message(
        ca_id=ca.id,
        client_id=smb.id,
        sender_role="ca",
        content="Please upload your GST certificate.",
    )
    db.add(m)
    await db.flush()
    return m


async def _invoice(db, ca: CAProfile, smb: SMBProfile) -> Invoice:
    inv = Invoice(
        ca_id=ca.id,
        client_id=smb.id,
        invoice_number=f"INV-{uuid.uuid4().hex[:8].upper()}",
        line_items=[{"description": "Monthly retainer", "amount": 5000}],
        subtotal=5000,
        gst_amount=900,
        total_amount=5900,
    )
    db.add(inv)
    await db.flush()
    return inv


async def _health_score(db, smb: SMBProfile, score: int = 80) -> HealthScore:
    hs = HealthScore(client_id=smb.id, score=score)
    db.add(hs)
    await db.flush()
    return hs


async def _notification(db, user: User) -> Notification:
    n = Notification(
        user_id=user.id,
        notification_type="sms",
        content="Your OTP is 123456",
    )
    db.add(n)
    await db.flush()
    return n


async def _payment(db, invoice: Invoice) -> Payment:
    p = Payment(
        invoice_id=invoice.id,
        razorpay_payment_id=f"pay_{uuid.uuid4().hex[:16]}",
        amount=590000,  # paise
        status="captured",
        method="upi",
    )
    db.add(p)
    await db.flush()
    return p


async def _regulation(db) -> Regulation:
    r = Regulation(
        title="New GST circular",
        compliance_type="gst",
        action_required_by=date(2025, 9, 30),
    )
    db.add(r)
    await db.flush()
    return r


# ===========================================================================
# User
# ===========================================================================

async def test_user_create_and_query(db_session):
    u = await _user(db_session, "9100000100", "ca")
    result = await db_session.execute(select(User).where(User.mobile == "9100000100"))
    fetched = result.scalar_one()
    assert fetched.id == u.id
    assert fetched.role == "ca"
    assert fetched.is_active is True


async def test_user_default_is_active(db_session):
    u = await _user(db_session, "9100000101")
    assert u.is_active is True


async def test_user_mobile_unique_constraint(db_session):
    await _user(db_session, "9100000102")
    with pytest.raises(IntegrityError):
        await _user(db_session, "9100000102")


async def test_user_invalid_role_raises(db_session):
    u = User(mobile="9100000103", role="admin", full_name="Bad Role")
    db_session.add(u)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_user_both_roles_valid(db_session):
    ca = await _user(db_session, "9100000104", "ca")
    smb = await _user(db_session, "9100000105", "smb")
    assert ca.role == "ca"
    assert smb.role == "smb"


async def test_user_created_at_is_datetime(db_session):
    u = await _user(db_session, "9100000106")
    assert isinstance(u.created_at, datetime)


# ===========================================================================
# CAProfile
# ===========================================================================

async def test_ca_profile_create_and_query(db_session):
    user = await _user(db_session, "9100000200", "ca")
    ca = await _ca(db_session, user)
    result = await db_session.execute(select(CAProfile).where(CAProfile.user_id == user.id))
    assert result.scalar_one().id == ca.id


async def test_ca_profile_default_plan_is_starter(db_session):
    user = await _user(db_session, "9100000201", "ca")
    ca = await _ca(db_session, user)
    assert ca.plan == "starter"


async def test_ca_profile_invalid_plan_raises(db_session):
    user = await _user(db_session, "9100000202", "ca")
    p = CAProfile(user_id=user.id, plan="enterprise")
    db_session.add(p)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_ca_profile_all_valid_plans(db_session):
    for i, plan in enumerate(["starter", "growth", "pro", "firm"]):
        user = await _user(db_session, f"910000020{3 + i}", "ca")
        p = CAProfile(user_id=user.id, plan=plan)
        db_session.add(p)
        await db_session.flush()
        assert p.plan == plan


async def test_ca_profile_icai_number_unique(db_session):
    user1 = await _user(db_session, "9100000210", "ca")
    user2 = await _user(db_session, "9100000211", "ca")
    p1 = CAProfile(user_id=user1.id, icai_number="ICAI12345")
    p2 = CAProfile(user_id=user2.id, icai_number="ICAI12345")
    db_session.add(p1)
    await db_session.flush()
    db_session.add(p2)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_ca_profile_cascade_delete(db_session):
    user = await _user(db_session, "9100000212", "ca")
    ca = await _ca(db_session, user)
    ca_id = ca.id

    await db_session.delete(user)
    await db_session.flush()

    result = await db_session.execute(select(CAProfile).where(CAProfile.id == ca_id))
    assert result.scalar_one_or_none() is None


# ===========================================================================
# SMBProfile
# ===========================================================================

async def test_smb_profile_create_and_query(db_session):
    user = await _user(db_session, "9100000300", "smb")
    smb = await _smb(db_session, user)
    result = await db_session.execute(select(SMBProfile).where(SMBProfile.user_id == user.id))
    assert result.scalar_one().id == smb.id


async def test_smb_profile_cascade_delete(db_session):
    user = await _user(db_session, "9100000301", "smb")
    smb = await _smb(db_session, user)
    smb_id = smb.id

    await db_session.delete(user)
    await db_session.flush()

    result = await db_session.execute(select(SMBProfile).where(SMBProfile.id == smb_id))
    assert result.scalar_one_or_none() is None


async def test_smb_profile_array_fields_stored_correctly(db_session):
    user = await _user(db_session, "9100000302", "smb")
    smb = SMBProfile(
        user_id=user.id,
        company_name="Tech Pvt Ltd",
        sectors=["technology", "saas"],
        states=["Maharashtra", "Karnataka"],
    )
    db_session.add(smb)
    await db_session.flush()

    result = await db_session.execute(select(SMBProfile).where(SMBProfile.id == smb.id))
    fetched = result.scalar_one()
    assert fetched.sectors == ["technology", "saas"]
    assert fetched.states == ["Maharashtra", "Karnataka"]


async def test_smb_profile_boolean_defaults(db_session):
    user = await _user(db_session, "9100000303", "smb")
    smb = await _smb(db_session, user)
    assert smb.gst_registered is False
    assert smb.gst_composition is False
    assert smb.has_factory is False
    assert smb.import_export is False
    assert smb.is_listed is False


# ===========================================================================
# CAClientLink
# ===========================================================================

async def test_ca_client_link_create(db_session):
    ca_user = await _user(db_session, "9100000400", "ca")
    smb_user = await _user(db_session, "9100000401", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    lnk = await _link(db_session, ca, smb, status="pending")
    assert lnk.status == "pending"


async def test_ca_client_link_default_status_is_pending(db_session):
    ca_user = await _user(db_session, "9100000402", "ca")
    smb_user = await _user(db_session, "9100000403", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    lnk = CAClientLink(ca_id=ca.id, client_id=smb.id)
    db_session.add(lnk)
    await db_session.flush()
    assert lnk.status == "pending"


async def test_ca_client_link_unique_pair(db_session):
    ca_user = await _user(db_session, "9100000404", "ca")
    smb_user = await _user(db_session, "9100000405", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    await _link(db_session, ca, smb)
    with pytest.raises(IntegrityError):
        await _link(db_session, ca, smb)


async def test_ca_client_link_invalid_status_raises(db_session):
    ca_user = await _user(db_session, "9100000406", "ca")
    smb_user = await _user(db_session, "9100000407", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    lnk = CAClientLink(ca_id=ca.id, client_id=smb.id, status="blocked")
    db_session.add(lnk)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_ca_client_link_all_valid_statuses(db_session):
    for i, status in enumerate(["pending", "active", "removed"]):
        ca_user = await _user(db_session, f"910000041{i}", "ca")
        smb_user = await _user(db_session, f"910000042{i}", "smb")
        ca = await _ca(db_session, ca_user)
        smb = await _smb(db_session, smb_user)
        lnk = await _link(db_session, ca, smb, status=status)
        assert lnk.status == status


# ===========================================================================
# ComplianceItem + ClientComplianceItem
# ===========================================================================

async def test_compliance_item_create_and_query(db_session):
    ci = await _compliance_item(db_session)
    result = await db_session.execute(select(ComplianceItem).where(ComplianceItem.id == ci.id))
    fetched = result.scalar_one()
    assert fetched.name == "GST Monthly GSTR-3B"
    assert fetched.is_active is True


async def test_compliance_item_jsonb_field(db_session):
    ci = ComplianceItem(
        id="TDS_QUARTERLY",
        name="TDS Quarterly Return",
        compliance_type="tds",
        applicable_conditions={"turnover_min": 5000000, "sectors": ["all"]},
    )
    db_session.add(ci)
    await db_session.flush()
    result = await db_session.execute(select(ComplianceItem).where(ComplianceItem.id == "TDS_QUARTERLY"))
    fetched = result.scalar_one()
    assert fetched.applicable_conditions["turnover_min"] == 5000000


async def test_client_compliance_item_create(db_session):
    ca_user = await _user(db_session, "9100000500", "ca")
    smb_user = await _user(db_session, "9100000501", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    item = await _compliance_item(db_session)
    cci = await _client_compliance(db_session, smb, ca, item)
    assert cci.status == "pending"
    assert cci.financial_year == "2025-26"


async def test_client_compliance_item_due_date_is_date_not_datetime(db_session):
    ca_user = await _user(db_session, "9100000502", "ca")
    smb_user = await _user(db_session, "9100000503", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    item = await _compliance_item(db_session, item_id="ITEM_DATE_TEST")
    cci = await _client_compliance(db_session, smb, ca, item)

    result = await db_session.execute(select(ClientComplianceItem).where(ClientComplianceItem.id == cci.id))
    fetched = result.scalar_one()
    assert isinstance(fetched.due_date, date)
    assert not isinstance(fetched.due_date, datetime)


async def test_client_compliance_item_invalid_status_raises(db_session):
    ca_user = await _user(db_session, "9100000504", "ca")
    smb_user = await _user(db_session, "9100000505", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    item = await _compliance_item(db_session, item_id="ITEM_BAD_STATUS")
    cci = ClientComplianceItem(
        client_id=smb.id,
        ca_id=ca.id,
        compliance_item_id=item.id,
        financial_year="2025-26",
        due_date=date(2025, 7, 20),
        status="approved",  # not a valid status
    )
    db_session.add(cci)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_client_compliance_item_all_valid_statuses(db_session):
    valid = ["pending", "in_progress", "waiting_on_client", "filed", "not_applicable", "overdue"]
    ca_user = await _user(db_session, "9100000510", "ca")
    smb_user = await _user(db_session, "9100000511", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    for i, status in enumerate(valid):
        item = await _compliance_item(db_session, item_id=f"ITEM_STATUS_{i}")
        cci = ClientComplianceItem(
            client_id=smb.id,
            ca_id=ca.id,
            compliance_item_id=item.id,
            financial_year="2025-26",
            due_date=date(2025, 7, 20),
            status=status,
        )
        db_session.add(cci)
        await db_session.flush()
        assert cci.status == status


# ===========================================================================
# Task
# ===========================================================================

async def test_task_create(db_session):
    ca_user = await _user(db_session, "9100000600", "ca")
    smb_user = await _user(db_session, "9100000601", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    t = await _task(db_session, ca, smb)
    assert t.title == "Collect bank statements"
    assert t.status == "pending"


async def test_task_due_date_is_date_not_datetime(db_session):
    ca_user = await _user(db_session, "9100000602", "ca")
    smb_user = await _user(db_session, "9100000603", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    t = Task(
        ca_id=ca.id,
        client_id=smb.id,
        title="Test task",
        assigned_to="ca",
        status="pending",
        created_by="ca",
        due_date=date(2025, 8, 31),
    )
    db_session.add(t)
    await db_session.flush()

    result = await db_session.execute(select(Task).where(Task.id == t.id))
    fetched = result.scalar_one()
    assert isinstance(fetched.due_date, date)
    assert not isinstance(fetched.due_date, datetime)


async def test_task_invalid_status_raises(db_session):
    ca_user = await _user(db_session, "9100000604", "ca")
    smb_user = await _user(db_session, "9100000605", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    t = Task(ca_id=ca.id, client_id=smb.id, title="Bad status", status="invalid_status",
             assigned_to="ca", created_by="ca")
    db_session.add(t)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_task_invalid_assigned_to_raises(db_session):
    ca_user = await _user(db_session, "9100000606", "ca")
    smb_user = await _user(db_session, "9100000607", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    t = Task(ca_id=ca.id, client_id=smb.id, title="Bad assigned_to",
             status="pending", assigned_to="admin", created_by="ca")
    db_session.add(t)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_task_invalid_created_by_raises(db_session):
    ca_user = await _user(db_session, "9100000608", "ca")
    smb_user = await _user(db_session, "9100000609", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    t = Task(ca_id=ca.id, client_id=smb.id, title="Bad created_by",
             status="pending", assigned_to="ca", created_by="bot")
    db_session.add(t)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_task_all_valid_statuses(db_session):
    ca_user = await _user(db_session, "9100000620", "ca")
    smb_user = await _user(db_session, "9100000621", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    for status in ["pending", "in_progress", "waiting_on_client", "done", "cancelled"]:
        t = Task(ca_id=ca.id, client_id=smb.id, title=f"Task {status}",
                 status=status, assigned_to="ca", created_by="ca")
        db_session.add(t)
        await db_session.flush()


# ===========================================================================
# Document
# ===========================================================================

async def test_document_create(db_session):
    ca_user = await _user(db_session, "9100000700", "ca")
    smb_user = await _user(db_session, "9100000701", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    doc = await _document(db_session, smb, ca)
    assert doc.is_deleted is False
    assert doc.file_name == "bank_statement.pdf"


async def test_document_is_deleted_defaults_false(db_session):
    ca_user = await _user(db_session, "9100000702", "ca")
    smb_user = await _user(db_session, "9100000703", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    doc = await _document(db_session, smb, ca)
    assert doc.is_deleted is False


async def test_document_r2_key_unique(db_session):
    ca_user = await _user(db_session, "9100000704", "ca")
    smb_user = await _user(db_session, "9100000705", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    r2_key = "docs/unique-key.pdf"
    d1 = Document(client_id=smb.id, file_name="a.pdf", file_size_bytes=1000,
                  mime_type="application/pdf", r2_key=r2_key, uploaded_by="client")
    d2 = Document(client_id=smb.id, file_name="b.pdf", file_size_bytes=2000,
                  mime_type="application/pdf", r2_key=r2_key, uploaded_by="client")
    db_session.add(d1)
    await db_session.flush()
    db_session.add(d2)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_document_invalid_uploaded_by_raises(db_session):
    smb_user = await _user(db_session, "9100000706", "smb")
    smb = await _smb(db_session, smb_user)
    d = Document(client_id=smb.id, file_name="x.pdf", file_size_bytes=100,
                 mime_type="application/pdf", r2_key="docs/x.pdf", uploaded_by="admin")
    db_session.add(d)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_document_soft_delete_flag(db_session):
    ca_user = await _user(db_session, "9100000708", "ca")
    smb_user = await _user(db_session, "9100000709", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    doc = await _document(db_session, smb, ca)
    doc.is_deleted = True
    await db_session.flush()

    result = await db_session.execute(select(Document).where(Document.id == doc.id))
    assert result.scalar_one().is_deleted is True


# ===========================================================================
# Message
# ===========================================================================

async def test_message_create(db_session):
    ca_user = await _user(db_session, "9100000800", "ca")
    smb_user = await _user(db_session, "9100000801", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    msg = await _message(db_session, ca, smb)
    assert msg.is_read is False
    assert msg.content == "Please upload your GST certificate."


async def test_message_invalid_sender_role_raises(db_session):
    ca_user = await _user(db_session, "9100000802", "ca")
    smb_user = await _user(db_session, "9100000803", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    m = Message(ca_id=ca.id, client_id=smb.id, sender_role="admin", content="Hi")
    db_session.add(m)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_message_is_read_defaults_false(db_session):
    ca_user = await _user(db_session, "9100000804", "ca")
    smb_user = await _user(db_session, "9100000805", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    msg = await _message(db_session, ca, smb)
    assert msg.is_read is False


async def test_message_both_sender_roles_valid(db_session):
    ca_user = await _user(db_session, "9100000806", "ca")
    smb_user = await _user(db_session, "9100000807", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    for role in ["ca", "client"]:
        m = Message(ca_id=ca.id, client_id=smb.id, sender_role=role, content=f"From {role}")
        db_session.add(m)
        await db_session.flush()


# ===========================================================================
# Invoice
# ===========================================================================

async def test_invoice_create(db_session):
    ca_user = await _user(db_session, "9100000900", "ca")
    smb_user = await _user(db_session, "9100000901", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    inv = await _invoice(db_session, ca, smb)
    assert inv.status == "draft"
    assert inv.gst_rate == 18


async def test_invoice_number_unique(db_session):
    ca_user = await _user(db_session, "9100000902", "ca")
    smb_user = await _user(db_session, "9100000903", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    shared_number = "INV-DUPLICATE"
    i1 = Invoice(ca_id=ca.id, client_id=smb.id, invoice_number=shared_number,
                 line_items=[], subtotal=0, gst_amount=0, total_amount=0)
    i2 = Invoice(ca_id=ca.id, client_id=smb.id, invoice_number=shared_number,
                 line_items=[], subtotal=0, gst_amount=0, total_amount=0)
    db_session.add(i1)
    await db_session.flush()
    db_session.add(i2)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_invoice_invalid_status_raises(db_session):
    ca_user = await _user(db_session, "9100000904", "ca")
    smb_user = await _user(db_session, "9100000905", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    inv = Invoice(ca_id=ca.id, client_id=smb.id, invoice_number="INV-BAD",
                  line_items=[], subtotal=0, gst_amount=0, total_amount=0, status="void")
    db_session.add(inv)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_invoice_due_date_is_date_not_datetime(db_session):
    ca_user = await _user(db_session, "9100000906", "ca")
    smb_user = await _user(db_session, "9100000907", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    inv = Invoice(
        ca_id=ca.id, client_id=smb.id, invoice_number="INV-DATE",
        line_items=[], subtotal=0, gst_amount=0, total_amount=0,
        due_date=date(2025, 8, 31),
    )
    db_session.add(inv)
    await db_session.flush()

    result = await db_session.execute(select(Invoice).where(Invoice.id == inv.id))
    fetched = result.scalar_one()
    assert isinstance(fetched.due_date, date)
    assert not isinstance(fetched.due_date, datetime)


async def test_invoice_all_valid_statuses(db_session):
    ca_user = await _user(db_session, "9100000910", "ca")
    smb_user = await _user(db_session, "9100000911", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    for i, status in enumerate(["draft", "sent", "paid", "overdue", "cancelled"]):
        inv = Invoice(ca_id=ca.id, client_id=smb.id, invoice_number=f"INV-{status}",
                      line_items=[], subtotal=0, gst_amount=0, total_amount=0, status=status)
        db_session.add(inv)
        await db_session.flush()


# ===========================================================================
# HealthScore
# ===========================================================================

async def test_health_score_create(db_session):
    smb_user = await _user(db_session, "9100001000", "smb")
    smb = await _smb(db_session, smb_user)
    hs = await _health_score(db_session, smb, score=75)
    assert hs.score == 75


async def test_health_score_max_boundary(db_session):
    smb_user = await _user(db_session, "9100001001", "smb")
    smb = await _smb(db_session, smb_user)
    hs = await _health_score(db_session, smb, score=100)
    assert hs.score == 100


async def test_health_score_min_boundary(db_session):
    smb_user = await _user(db_session, "9100001002", "smb")
    smb = await _smb(db_session, smb_user)
    hs = await _health_score(db_session, smb, score=0)
    assert hs.score == 0


async def test_health_score_above_100_raises(db_session):
    smb_user = await _user(db_session, "9100001003", "smb")
    smb = await _smb(db_session, smb_user)
    hs = HealthScore(client_id=smb.id, score=101)
    db_session.add(hs)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_health_score_below_0_raises(db_session):
    smb_user = await _user(db_session, "9100001004", "smb")
    smb = await _smb(db_session, smb_user)
    hs = HealthScore(client_id=smb.id, score=-1)
    db_session.add(hs)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_health_score_breakdown_jsonb(db_session):
    smb_user = await _user(db_session, "9100001005", "smb")
    smb = await _smb(db_session, smb_user)
    breakdown = {"gst": 30, "tds": 25, "roc": 20}
    hs = HealthScore(client_id=smb.id, score=75, breakdown=breakdown)
    db_session.add(hs)
    await db_session.flush()
    result = await db_session.execute(select(HealthScore).where(HealthScore.id == hs.id))
    assert result.scalar_one().breakdown["gst"] == 30


# ===========================================================================
# Payment
# ===========================================================================

async def test_payment_create(db_session):
    ca_user = await _user(db_session, "9100001100", "ca")
    smb_user = await _user(db_session, "9100001101", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    inv = await _invoice(db_session, ca, smb)
    pay = await _payment(db_session, inv)
    assert pay.status == "captured"
    assert pay.amount == 590000


async def test_payment_razorpay_id_unique(db_session):
    ca_user = await _user(db_session, "9100001102", "ca")
    smb_user = await _user(db_session, "9100001103", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    inv = await _invoice(db_session, ca, smb)
    pay_id = "pay_DUPLICATE0000"
    p1 = Payment(invoice_id=inv.id, razorpay_payment_id=pay_id, amount=100, status="captured")
    db_session.add(p1)
    await db_session.flush()
    p2 = Payment(invoice_id=inv.id, razorpay_payment_id=pay_id, amount=100, status="captured")
    db_session.add(p2)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_payment_invalid_status_raises(db_session):
    ca_user = await _user(db_session, "9100001104", "ca")
    smb_user = await _user(db_session, "9100001105", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    inv = await _invoice(db_session, ca, smb)
    p = Payment(invoice_id=inv.id, razorpay_payment_id="pay_BAD", amount=100, status="pending")
    db_session.add(p)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_payment_all_valid_statuses(db_session):
    ca_user = await _user(db_session, "9100001110", "ca")
    smb_user = await _user(db_session, "9100001111", "smb")
    ca = await _ca(db_session, ca_user)
    smb = await _smb(db_session, smb_user)
    for i, status in enumerate(["captured", "failed", "refunded"]):
        inv = await _invoice(db_session, ca, smb)
        p = Payment(invoice_id=inv.id, razorpay_payment_id=f"pay_{status}_{i}",
                    amount=100, status=status)
        db_session.add(p)
        await db_session.flush()


# ===========================================================================
# Regulation
# ===========================================================================

async def test_regulation_create(db_session):
    reg = await _regulation(db_session)
    result = await db_session.execute(select(Regulation).where(Regulation.id == reg.id))
    fetched = result.scalar_one()
    assert fetched.title == "New GST circular"
    assert fetched.is_classified is False


async def test_regulation_action_required_by_is_date(db_session):
    reg = await _regulation(db_session)
    result = await db_session.execute(select(Regulation).where(Regulation.id == reg.id))
    fetched = result.scalar_one()
    assert isinstance(fetched.action_required_by, date)
    assert not isinstance(fetched.action_required_by, datetime)


# ===========================================================================
# Notification
# ===========================================================================

async def test_notification_create(db_session):
    user = await _user(db_session, "9100001200", "ca")
    n = await _notification(db_session, user)
    assert n.status == "pending"
    assert n.notification_type == "sms"


async def test_notification_default_status_is_pending(db_session):
    user = await _user(db_session, "9100001201", "ca")
    n = await _notification(db_session, user)
    assert n.status == "pending"


async def test_notification_invalid_type_raises(db_session):
    user = await _user(db_session, "9100001202", "ca")
    n = Notification(user_id=user.id, notification_type="telegram", content="Hi")
    db_session.add(n)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_notification_invalid_status_raises(db_session):
    user = await _user(db_session, "9100001203", "ca")
    n = Notification(user_id=user.id, notification_type="sms", content="Hi", status="bounced")
    db_session.add(n)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_notification_all_valid_types(db_session):
    user = await _user(db_session, "9100001210", "ca")
    for ntype in ["whatsapp", "push", "email", "sms"]:
        n = Notification(user_id=user.id, notification_type=ntype, content="test")
        db_session.add(n)
        await db_session.flush()


async def test_notification_all_valid_statuses(db_session):
    user = await _user(db_session, "9100001211", "ca")
    for status in ["pending", "sent", "delivered", "failed", "read"]:
        n = Notification(user_id=user.id, notification_type="sms",
                         content="test", status=status)
        db_session.add(n)
        await db_session.flush()
