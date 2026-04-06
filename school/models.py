# school/models.py

from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, post_delete
from simple_history.models import HistoricalRecords
from django.dispatch import receiver
import datetime


# =============================================================
# NEW: GRADE LEVEL TABLE
# The master lookup table for grades and their tuition fees.
# Every grade lives here. Students link to this table.
# =============================================================

class GradeLevel(models.Model):
    """
    A master table of all grade levels in the school.
    Each grade has a defined tuition fee.
    When a student is assigned to a grade, their Finance record
    automatically inherits the tuition amount from here.
    """

    name = models.CharField(
        max_length=100,
        unique=True,    # No duplicate grade names
        help_text="e.g. Grade 1, JSS 2, SS 3, Primary 4"
    )

    tuition_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Total school fees for this grade level (e.g. 150000.00)"
    )

    description = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional note, e.g. 'Junior Secondary — Science track'"
    )

    order = models.PositiveIntegerField(
        default=0,
        help_text="Controls the display order. Lower number = appears first."
    )
    
    history = HistoricalRecords()
    
    def __str__(self):
        # e.g. "JSS 2 — L$85,000.00"
        return f"{self.name} — L${self.tuition_fee:,.2f}"

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Grade Level"
        verbose_name_plural = "Grade Levels & Tuition"


# =============================================================
# MODULE 1: STUDENT (UPDATED)
# Added: gender field
# Changed: grade_level is now a ForeignKey to GradeLevel
# =============================================================

class Student(models.Model):
    """
    Represents a student enrolled in the school.
    grade_level is now a ForeignKey — it links to the GradeLevel
    table so tuition fees are inherited automatically.
    """

    GENDER_CHOICES = [
        ('male',   'Male'),
        ('female', 'Female'),
        ('other',  'Other'),
    ]

    student_name = models.CharField(
        max_length=200,
        help_text="Full name of the student"
    )

    gender = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES,
        default='male',
        help_text="Student's gender"
    )

    # CHANGED: was CharField, now ForeignKey to GradeLevel
    # on_delete=PROTECT means you cannot delete a grade that
    # still has students assigned to it — prevents accidents
    grade_level = models.ForeignKey(
        GradeLevel,
        on_delete=models.PROTECT,
        related_name='students',
        help_text="Select the student's grade — tuition will be set automatically"
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck if student has left the school"
    )

    date_enrolled = models.DateField(
        auto_now_add=True
    )
    
    history = HistoricalRecords()
    
    def __str__(self):
        return f"{self.student_name} ({self.grade_level.name})"

    class Meta:
        ordering = ['student_name']
        verbose_name = "Student"
        verbose_name_plural = "Students"


# =============================================================
# SIGNAL: AUTO-CREATE & AUTO-UPDATE FINANCE RECORD
# This runs automatically every time a Student is saved.
# It creates or updates the Finance record with the correct
# tuition fee from the student's GradeLevel.
# =============================================================

@receiver(post_save, sender=Student)
def sync_student_finance(sender, instance, created, **kwargs):
    tuition = instance.grade_level.tuition_fee
    if created:
        Finance.objects.create(
            student        = instance,
            total_fees_due = tuition,
            amount_paid    = 0.00,
            payment_status = 'unpaid',
        )
    else:
        try:
            finance = instance.finance
            if finance.total_fees_due != tuition:
                finance.total_fees_due = tuition
                if finance.amount_paid > tuition:
                    finance.amount_paid = tuition
                finance.payment_status = finance._compute_status()
                finance.save()
        except Finance.DoesNotExist:
            Finance.objects.create(
                student        = instance,
                total_fees_due = tuition,
                amount_paid    = 0.00,
                payment_status = 'unpaid',
            )

# =============================================================
# MODULE 2: FINANCE (UPDATED)
# Added: overpayment validation
# Added: _compute_status() helper to auto-set payment_status
# total_fees_due is now auto-populated from GradeLevel signal
# =============================================================

class Finance(models.Model):
    """
    Tracks fee payments for each student.
    total_fees_due is automatically set from the student's
    GradeLevel tuition fee — staff should not change it manually.
    """

    PAYMENT_STATUS_CHOICES = [
        ('fully_paid', 'Fully Paid'),
        ('partial',    'Partial'),
        ('unpaid',     'Unpaid'),
    ]

    student = models.OneToOneField(
        Student,
        on_delete=models.CASCADE,
        related_name='finance',
    )

    # This field is populated automatically from GradeLevel.tuition_fee
    # via the post_save signal above. Staff should not edit this directly.
    total_fees_due = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Auto-populated from the student's grade level tuition fee"
    )

    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0.00,
        help_text="Total amount paid so far — cannot exceed total fees due"
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='unpaid',
    )

    last_payment_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of the most recent payment"
    )
    
    history = HistoricalRecords()

    def _compute_status(self):
        """
        Returns the correct payment status string based on
        how much has been paid vs what is owed.
        Called automatically before every save.
        """
        if self.amount_paid <= 0:
            return 'unpaid'
        elif self.amount_paid >= self.total_fees_due:
            return 'fully_paid'
        else:
            return 'partial'

    def balance(self):
        """How much the student still owes."""
        return self.total_fees_due - self.amount_paid

   
# NEW CLEAN | April 04, 2026 |  the existing clean() method with this updated version:
    def clean(self):
        """..."""
        if self.amount_paid is not None and self.total_fees_due is not None:
            if self.amount_paid < 0:
                raise ValidationError({
                    'amount_paid': 'Amount paid cannot be negative.'
                })
            if self.amount_paid > self.total_fees_due:
                raise ValidationError({
                    'amount_paid': (
                        f'Amount paid (L${self.amount_paid:,.2f}) cannot exceed '
                        f'total fees due (L${self.total_fees_due:,.2f}).'
                    )
                })

    def save(self, *args, **kwargs):       # ← back to class level ✅
        self.full_clean()
        self.payment_status = self._compute_status()
        super().save(*args, **kwargs)

    def __str__(self):                     # ← back to class level ✅
        return f"{self.student.student_name} — {self.get_payment_status_display()}"

    class Meta:                            # ← back to class level ✅
        ordering = ['student__student_name']
        verbose_name = "Finance Record"
        verbose_name_plural = "Finance Records"

    def balance(self):
        """How much the student still owes."""
        if self.total_fees_due is None or self.amount_paid is None:
            return 0
        return self.total_fees_due - self.amount_paid      
        
#New model | April 04, 2026|  for payment transactions, linked to Finance. Each payment updates the Finance record automatically. 
class PaymentTransaction(models.Model):
    
    finance = models.ForeignKey(
        Finance,
        on_delete=models.CASCADE,
        related_name='transactions',  # finance.transactions.all()
        help_text="The student's finance record this payment applies to"
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Amount received in this single installment"
    )

    date = models.DateField(
        default=timezone.now,
        help_text="Date this payment was received"
    )

    received_by = models.CharField(
        max_length=100,
        help_text="Name of the staff member (Bursar) who collected this payment"
    )

    receipt_number = models.CharField(
        max_length=30,
        unique=True,
        blank=True,        # We auto-generate this on save
        help_text="Auto-generated receipt number — do not edit manually"
    )

    payment_method = models.CharField(
        max_length=20,
        choices=[
            ('cash',     'Cash'),
            ('transfer', 'Bank Transfer'),
            ('cheque',   'Cheque'),
            ('pos',      'POS / Card'),
        ],
        default='cash',
    )

    notes = models.TextField(
        blank=True,
        help_text="Optional: any notes about this payment (e.g. 'Part payment for first term')"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()
    
    def save(self, *args, **kwargs):
        """
        Override save() to:
        1. Auto-generate a unique receipt number if not set
        2. Save the transaction
        3. Recalculate Finance.amount_paid from all transactions
        """
        # ── Auto-generate receipt number ──────────────────────
        if not self.receipt_number:
            self.receipt_number = self._generate_receipt_number()

        super().save(*args, **kwargs)

        # ── Sync Finance.amount_paid with sum of all transactions
        self._sync_finance()

    def delete(self, *args, **kwargs):
        """
        When a transaction is deleted, recalculate the Finance balance.
        """
        finance = self.finance
        super().delete(*args, **kwargs)
        # Recalculate after deletion
        self._sync_finance_instance(finance)

    def _generate_receipt_number(self):
        """
        Generates a receipt number in the format:
        RCP-2025-0001
        RCP-2025-0002
        ... etc.
        Thread-safe via select_for_update would be needed in production,
        but this works perfectly for a school system.
        """
        import datetime
        year = datetime.date.today().year

        # Find the highest receipt number for this year
        last = (
            PaymentTransaction.objects
            .filter(receipt_number__startswith=f'RCP-{year}-')
            .order_by('-receipt_number')
            .first()
        )

        if last and last.receipt_number:
            try:
                # Extract the sequence number and increment it
                last_seq = int(last.receipt_number.split('-')[-1])
                new_seq = last_seq + 1
            except (ValueError, IndexError):
                new_seq = 1
        else:
            new_seq = 1

        return f'RCP-{year}-{new_seq:04d}'   # e.g. RCP-2025-0001

    def _sync_finance(self):
        """Recalculate Finance.amount_paid from all transactions."""
        self._sync_finance_instance(self.finance)

    @staticmethod
    def _sync_finance_instance(finance):
        """
        Recalculate and save Finance.amount_paid.
        Called after any transaction save or delete.
        Uses aggregate SUM for accuracy.
        """
        from django.db.models import Sum as DSum
        total = (
            PaymentTransaction.objects
            .filter(finance=finance)
            .aggregate(total=DSum('amount'))['total']
        ) or 0

        # Cap at total_fees_due — cannot overpay
        if total > finance.total_fees_due:
            total = finance.total_fees_due

        # Use update() to avoid triggering Finance.save() signal loop
        Finance.objects.filter(pk=finance.pk).update(
            amount_paid    = total,
            payment_status = _compute_payment_status(total, finance.total_fees_due),
        )

    def __str__(self):
        return (
            f"{self.receipt_number} — "
            f"{self.finance.student.student_name} — "
            f"L${self.amount:,.2f} on {self.date}"
        )

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = "Payment Transaction"
        verbose_name_plural = "Payment Transactions"


# ── Helper function (used by _sync_finance_instance) ─────────
def _compute_payment_status(amount_paid, total_fees_due):
    """
    Returns the correct payment status string.
    Standalone function so it can be called without a Finance instance.
    """
    if amount_paid <= 0:
        return 'unpaid'
    elif amount_paid >= total_fees_due:
        return 'fully_paid'
    else:
        return 'partial'
    
# =============================================================
# MODULE 3: ACADEMIC CALENDAR (unchanged)
# =============================================================

class AcademicCalendar(models.Model):

    EVENT_TYPE_CHOICES = [
        ('test',     'Test / Exam'),
        ('trip',     'School Trip'),
        ('revision', 'Revision / Study Session'),
        ('holiday',  'Holiday / Break'),
        ('other',    'Other'),
    ]

    STATUS_CHOICES = [
        ('upcoming',    'Upcoming'),
        ('in_progress', 'In Progress'),
        ('completed',   'Completed'),
    ]

    event_name  = models.CharField(max_length=200)
    event_type  = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES, default='other')
    description = models.TextField(blank=True)
    start_date  = models.DateField()
    end_date    = models.DateField(null=True, blank=True)
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='upcoming')

    history = HistoricalRecords()
    
    def __str__(self):
        return f"{self.event_name} ({self.start_date})"

    class Meta:
        ordering = ['start_date']
        verbose_name = "Academic Event"
        verbose_name_plural = "Academic Calendar"


# =============================================================
# MODULE 4: DISCIPLINE (unchanged)
# =============================================================

class Discipline(models.Model):

    ACTION_CHOICES = [
        ('warning',    'Warning'),
        ('detention',  'Detention'),
        ('suspension', 'Suspension'),
        ('expulsion',  'Expulsion'),
    ]

    student      = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='discipline_records')
    action_taken = models.CharField(max_length=20, choices=ACTION_CHOICES)
    reason       = models.TextField()
    date         = models.DateField(default=timezone.now)
    issued_by    = models.CharField(max_length=100, blank=True)


    history = HistoricalRecords()

    def __str__(self):
        return f"{self.student.student_name} — {self.get_action_taken_display()} on {self.date}"

    class Meta:
        ordering = ['-date']
        verbose_name = "Discipline Record"
        verbose_name_plural = "Discipline Records"
        
        
# =============================================================
# AUDIT LOG  ← NEW MODEL
# Human-readable activity feed for the dashboard
# =============================================================

class AuditLog(models.Model):
    """
    A human-readable log of every significant action in the system.
    Written automatically by signals below — staff never touch this.

    This powers the "Recent Activity" feed on the proprietor dashboard.
    """

    ACTION_CHOICES = [
        ('create', 'Created'),
        ('update', 'Updated'),
        ('delete', 'Deleted'),
        ('login',  'Logged In'),
        ('payment','Payment Recorded'),
    ]

    # Which user performed the action (null for system actions)
    user = models.ForeignKey(
        User,
        on_delete   = models.SET_NULL,
        null        = True,
        blank       = True,
        related_name = 'audit_logs',
    )

    action      = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name  = models.CharField(max_length=50)   # e.g. "Student", "Finance"
    object_id   = models.PositiveIntegerField(null=True, blank=True)
    object_repr = models.CharField(max_length=300)  # Human-readable name of the object
    description = models.TextField()                # Full English sentence of what happened
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    timestamp   = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {self.user} — {self.description[:60]}"

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Audit Log Entry"
        verbose_name_plural = "Audit Log"


# =============================================================
# AUDIT SIGNALS
# These run automatically on every model save/delete and write
# a human-readable entry to the AuditLog table.
# =============================================================

def _get_current_user():
    """
    Gets the currently logged-in user from the request thread.
    simple_history's middleware stores it on the thread.
    Returns None if called outside a request (e.g. shell, migrations).
    """
    try:
        from simple_history.models import HistoricalRecords
        return HistoricalRecords.context.request.user
    except AttributeError:
        return None


def _write_audit(action, model_name, obj_id, obj_repr, description):
    """
    Helper: writes one AuditLog entry.
    Wraps in try/except so a logging failure never breaks the main action.
    """
    try:
        user = _get_current_user()
        AuditLog.objects.create(
            user        = user if (user and user.is_authenticated) else None,
            action      = action,
            model_name  = model_name,
            object_id   = obj_id,
            object_repr = obj_repr,
            description = description,
        )
    except Exception:
        pass    # Never let logging crash the app


# ── Student signals ───────────────────────────────────────────

@receiver(post_save, sender=Student)
def audit_student_save(sender, instance, created, **kwargs):
    action = 'create' if created else 'update'
    verb   = 'enrolled new student' if created else 'updated student record for'
    _write_audit(
        action      = action,
        model_name  = 'Student',
        obj_id      = instance.pk,
        obj_repr    = str(instance),
        description = (
            f"{verb} {instance.student_name} "
            f"(Grade: {instance.grade_level.name}, "
            f"Gender: {instance.get_gender_display()})"
        ),
    )

@receiver(post_delete, sender=Student)
def audit_student_delete(sender, instance, **kwargs):
    _write_audit(
        action      = 'delete',
        model_name  = 'Student',
        obj_id      = instance.pk,
        obj_repr    = str(instance),
        description = (
            f"deleted student {instance.student_name} "
            f"(Grade: {instance.grade_level.name})"
        ),
    )


# ── Finance signals ───────────────────────────────────────────

@receiver(post_save, sender=Finance)
def audit_finance_save(sender, instance, created, **kwargs):
    if created:
        return   # Created automatically — not a user action worth logging
    _write_audit(
        action      = 'update',
        model_name  = 'Finance',
        obj_id      = instance.pk,
        obj_repr    = str(instance),
        description = (
            f"updated finance record for {instance.student.student_name} — "
            f"Amount Paid: L${instance.amount_paid:,.2f} / "
            f"L${instance.total_fees_due:,.2f} "
            f"({instance.get_payment_status_display()})"
        ),
    )


# ── PaymentTransaction signals ────────────────────────────────

@receiver(post_save, sender=PaymentTransaction)
def audit_payment_save(sender, instance, created, **kwargs):
    if not created:
        return   # Only log new payments, not edits
    _write_audit(
        action      = 'payment',
        model_name  = 'PaymentTransaction',
        obj_id      = instance.pk,
        obj_repr    = instance.receipt_number,
        description = (
            f"recorded payment of L${instance.amount:,.2f} from "
            f"{instance.finance.student.student_name} "
            f"via {instance.get_payment_method_display()} "
            f"— Receipt {instance.receipt_number} "
            f"(collected by {instance.received_by})"
        ),
    )

@receiver(post_delete, sender=PaymentTransaction)
def audit_payment_delete(sender, instance, **kwargs):
    _write_audit(
        action      = 'delete',
        model_name  = 'PaymentTransaction',
        obj_id      = instance.pk,
        obj_repr    = instance.receipt_number,
        description = (
            f"deleted payment transaction {instance.receipt_number} "
            f"(L${instance.amount:,.2f} from "
            f"{instance.finance.student.student_name})"
        ),
    )


# ── Discipline signals ────────────────────────────────────────

@receiver(post_save, sender=Discipline)
def audit_discipline_save(sender, instance, created, **kwargs):
    action = 'create' if created else 'update'
    verb   = 'issued' if created else 'updated'
    _write_audit(
        action      = action,
        model_name  = 'Discipline',
        obj_id      = instance.pk,
        obj_repr    = str(instance),
        description = (
            f"{verb} {instance.get_action_taken_display()} for "
            f"{instance.student.student_name} — "
            f"Reason: {instance.reason[:80]}"
        ),
    )

@receiver(post_delete, sender=Discipline)
def audit_discipline_delete(sender, instance, **kwargs):
    _write_audit(
        action      = 'delete',
        model_name  = 'Discipline',
        obj_id      = instance.pk,
        obj_repr    = str(instance),
        description = (
            f"deleted discipline record for "
            f"{instance.student.student_name} "
            f"({instance.get_action_taken_display()} on {instance.date})"
        ),
    )


# ── AcademicCalendar signals ──────────────────────────────────

@receiver(post_save, sender=AcademicCalendar)
def audit_calendar_save(sender, instance, created, **kwargs):
    verb = 'added calendar event' if created else 'updated calendar event'
    _write_audit(
        action      = 'create' if created else 'update',
        model_name  = 'AcademicCalendar',
        obj_id      = instance.pk,
        obj_repr    = str(instance),
        description = (
            f"{verb}: {instance.event_name} "
            f"({instance.get_event_type_display()}) "
            f"on {instance.start_date}"
        ),
    )