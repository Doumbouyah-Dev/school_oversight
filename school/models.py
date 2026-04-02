# school/models.py

from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
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
    """
    Triggered automatically after any Student save.

    - If student is NEW       → create a Finance record with tuition from grade
    - If student's grade CHANGES → update total_fees_due to new grade's tuition
      (but only if the student hasn't already paid more — we protect them)
    """

    tuition = instance.grade_level.tuition_fee

    if created:
        # Brand new student — create their Finance record
        Finance.objects.create(
            student        = instance,
            total_fees_due = tuition,
            amount_paid    = 0.00,
            payment_status = 'unpaid',
        )
    else:
        # Existing student — update their Finance if grade changed
        try:
            finance = instance.finance  # OneToOne reverse accessor
            # Only update total_fees_due if the new tuition is different
            if finance.total_fees_due != tuition:
                finance.total_fees_due = tuition
                # If they've already paid more than the new fee, cap it
                if finance.amount_paid > tuition:
                    finance.amount_paid = tuition
                # Recalculate payment status automatically
                finance.payment_status = finance._compute_status()
                finance.save()
        except Finance.DoesNotExist:
            # Finance record is missing — create it
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

    def clean(self):
        """
        Django validation — runs before the record is saved.
        Raises a clear error if staff tries to enter an
        amount_paid greater than total_fees_due.
        """
        if self.amount_paid is not None and self.total_fees_due is not None:
            if self.amount_paid < 0:
                raise ValidationError({
                    'amount_paid': 'Amount paid cannot be negative.'
                })
            if self.amount_paid > self.total_fees_due:
                raise ValidationError({
                    'amount_paid': (
                        f'Amount paid (L${self.amount_paid:,.2f}) cannot exceed '
                        f'total fees due (L${self.total_fees_due:,.2f}). '
                        f'Maximum payable: L${self.total_fees_due:,.2f}.'
                    )
                })

    def save(self, *args, **kwargs):
        """
        Override save() to:
        1. Run validation (clean) before saving
        2. Auto-compute and set payment_status
        """
        self.full_clean()   # ← Triggers clean() above
        self.payment_status = self._compute_status()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.student_name} — {self.get_payment_status_display()}"

    class Meta:
        ordering = ['student__student_name']
        verbose_name = "Finance Record"
        verbose_name_plural = "Finance Records"


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

    def __str__(self):
        return f"{self.student.student_name} — {self.get_action_taken_display()} on {self.date}"

    class Meta:
        ordering = ['-date']
        verbose_name = "Discipline Record"
        verbose_name_plural = "Discipline Records"