
import io
import csv
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from typing import List, Optional
from pydantic import BaseModel

from app.db.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    User,
    Student,
    Subject,
    Section,
    RoleEnum,
    Assessment,
    StudentMark,
    CourseClass,
    AcademicYear,
    Branch,
    ProgramLeaderAssignment,
    FacultyAssignment,
)


router = APIRouter()


@router.get("/my-marks")
async def get_my_marks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != RoleEnum.STUDENT:
        raise HTTPException(
            status_code=403,
            detail="Only students can access this endpoint"
        )

    result = await db.execute(
        select(Student).where(Student.user_id == current_user.id)
    )
    student = result.scalars().first()

    if not student:
        raise HTTPException(
            status_code=404,
            detail="Student record not found"
        )

    result = await db.execute(
        select(StudentMark).where(StudentMark.student_id == student.id)
    )
    marks = result.scalars().all()

    report = []
    total_obtained = 0
    total_max = 0
    subjects_count = set()
    assessments_count = len(marks)

    for m in marks:
        result = await db.execute(
            select(Assessment).where(Assessment.id == m.assessment_id)
        )
        assessment = result.scalars().first()

        if not assessment:
            continue

        result = await db.execute(
            select(Subject).where(Subject.id == assessment.subject_id)
        )
        subject = result.scalars().first()

        subj_name = subject.name if subject else "Unknown Subject"
        subj_code = subject.code if subject else "UNK"

        subjects_count.add(assessment.subject_id)
        total_obtained += m.marks_obtained
        total_max += assessment.max_marks

        pct = (
            m.marks_obtained / assessment.max_marks * 100
            if assessment.max_marks > 0
            else 0
        )

        report.append({
            "id": m.id,
            "subject_name": subj_name,
            "subject_code": subj_code,
            "assessment_name": assessment.name,
            "max_marks": assessment.max_marks,
            "date": assessment.date,
            "obtained_marks": m.marks_obtained,
            "percentage": round(pct, 2)
        })

    overall_pct = (
        total_obtained / total_max * 100
        if total_max > 0
        else 0
    )

    result = await db.execute(
        select(CourseClass).where(CourseClass.id == student.class_id)
    )
    cls = result.scalars().first()

    result = await db.execute(
        select(Branch).where(Branch.id == student.branch_id)
    )
    br = result.scalars().first()

    result = await db.execute(
        select(Section).where(Section.id == student.section_id)
    )
    sec = result.scalars().first()

    return {
        "student": {
            "name": student.name,
            "enrollment_no": student.enrollment_no,
            "roll_number": student.roll_number,
            "class_name": cls.name if cls else "",
            "branch_name": br.name if br else "",
            "section_name": sec.name if sec else "",
            "year": student.year
        },
        "summary": {
            "overall_percentage": round(overall_pct, 2),
            "total_subjects": len(subjects_count),
            "total_assessments": assessments_count,
            "marks_obtained": total_obtained,
            "maximum_marks": total_max
        },
        "marks": sorted(
            report,
            key=lambda x: x["subject_name"]
        )
    }


class AssessmentCreate(BaseModel):
    subject_id: str
    section_id: str
    type: str
    max_marks: float
    date: Optional[str] = None


@router.get("/assessments")
async def get_assessments(
    section_id: str,
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role in [
        RoleEnum.PROGRAM_LEADER,
        RoleEnum.FACULTY
    ]:
        result = await db.execute(
            select(ProgramLeaderAssignment).where(
                ProgramLeaderAssignment.user_id == current_user.id
            )
        )
        scope = result.scalars().first()

        is_pl = (
            current_user.role == RoleEnum.PROGRAM_LEADER
            and scope
            and scope.section_id == section_id
        )

        result = await db.execute(
            select(FacultyAssignment).where(
                FacultyAssignment.faculty_id == current_user.id,
                FacultyAssignment.subject_id == subject_id,
                FacultyAssignment.section_id == section_id,
            )
        )
        assignment = result.scalars().first()

        is_faculty = assignment is not None

        if not is_pl and not is_faculty:
            raise HTTPException(
                status_code=403,
                detail="Not authorized"
            )

    result = await db.execute(
        select(Assessment)
        .where(
            Assessment.section_id == section_id,
            Assessment.subject_id == subject_id,
        )
        .order_by(Assessment.created_at.desc())
    )

    return result.scalars().all()


@router.post("/assessments")
async def create_assessment(
    data: AssessmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role in [
        RoleEnum.PROGRAM_LEADER,
        RoleEnum.FACULTY
    ]:
        result = await db.execute(
            select(ProgramLeaderAssignment).where(
                ProgramLeaderAssignment.user_id == current_user.id
            )
        )
        scope = result.scalars().first()

        is_pl = (
            current_user.role == RoleEnum.PROGRAM_LEADER
            and scope
            and scope.section_id == data.section_id
        )

        result = await db.execute(
            select(FacultyAssignment).where(
                FacultyAssignment.faculty_id == current_user.id,
                FacultyAssignment.subject_id == data.subject_id,
                FacultyAssignment.section_id == data.section_id,
            )
        )
        assignment = result.scalars().first()

        is_faculty = assignment is not None

        if not is_pl and not is_faculty:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to manage this subject's marks"
            )

    result = await db.execute(
        select(func.count())
        .select_from(Assessment)
        .where(
            Assessment.subject_id == data.subject_id,
            Assessment.section_id == data.section_id,
            Assessment.type == data.type,
        )
    )
    count = result.scalar() or 0
    seq = count + 1

    name_prefix = (
        data.type.split(" ")[0]
        if "Internal" in data.type
        else data.type
    )

    ass = Assessment(
        id=str(uuid.uuid4()),
        subject_id=data.subject_id,
        section_id=data.section_id,
        type=data.type,
        sequence_number=seq,
        name=f"{name_prefix} {seq}",
        max_marks=data.max_marks,
        date=data.date
    )

    db.add(ass)
    await db.commit()

    return {
        "id": ass.id,
        "subject_id": ass.subject_id,
        "section_id": ass.section_id,
        "type": ass.type,
        "sequence_number": ass.sequence_number,
        "name": ass.name,
        "max_marks": ass.max_marks,
        "date": ass.date
    }


class MarkEntry(BaseModel):
    student_id: str
    marks_obtained: float


class MarksSubmit(BaseModel):
    marks: List[MarkEntry]


@router.get("/assessments/{id}/marks")
async def get_assessment_marks(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Assessment).where(Assessment.id == id)
    )
    ass = result.scalars().first()

    if not ass:
        raise HTTPException(404, "Assessment not found")

    if current_user.role in [
        RoleEnum.PROGRAM_LEADER,
        RoleEnum.FACULTY
    ]:
        result = await db.execute(
            select(ProgramLeaderAssignment).where(
                ProgramLeaderAssignment.user_id == current_user.id
            )
        )
        scope = result.scalars().first()

        is_pl = (
            current_user.role == RoleEnum.PROGRAM_LEADER
            and scope
            and scope.section_id == ass.section_id
        )

        result = await db.execute(
            select(FacultyAssignment).where(
                FacultyAssignment.faculty_id == current_user.id,
                FacultyAssignment.subject_id == ass.subject_id,
                FacultyAssignment.section_id == ass.section_id,
            )
        )
        assignment = result.scalars().first()

        is_faculty = assignment is not None

        if not is_pl and not is_faculty:
            raise HTTPException(
                status_code=403,
                detail="Not authorized"
            )

    result = await db.execute(
        select(Student).where(Student.section_id == ass.section_id)
    )
    students = result.scalars().all()

    result = await db.execute(
        select(StudentMark).where(StudentMark.assessment_id == id)
    )
    existing_marks = {
        m.student_id: m
        for m in result.scalars().all()
    }

    res = []

    for s in students:
        mark_record = existing_marks.get(s.id)

        res.append({
            "student_id": s.id,
            "name": s.name,
            "enrollment_no": s.enrollment_no,
            "roll_number": s.roll_number,
            "marks_obtained": (
                mark_record.marks_obtained
                if mark_record
                else None
            )
        })

    return sorted(
        res,
        key=lambda x: (
            x["roll_number"] or "",
            x["name"]
        )
    )


@router.post("/assessments/{id}/marks")
async def submit_marks(
    id: str,
    data: MarksSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Assessment).where(Assessment.id == id)
    )
    ass = result.scalars().first()

    if not ass:
        raise HTTPException(404, "Assessment not found")

    if current_user.role in [
        RoleEnum.PROGRAM_LEADER,
        RoleEnum.FACULTY
    ]:
        result = await db.execute(
            select(ProgramLeaderAssignment).where(
                ProgramLeaderAssignment.user_id == current_user.id
            )
        )
        scope = result.scalars().first()

        is_pl = (
            current_user.role == RoleEnum.PROGRAM_LEADER
            and scope
            and scope.section_id == ass.section_id
        )

        result = await db.execute(
            select(FacultyAssignment).where(
                FacultyAssignment.faculty_id == current_user.id,
                FacultyAssignment.subject_id == ass.subject_id,
                FacultyAssignment.section_id == ass.section_id,
            )
        )
        assignment = result.scalars().first()

        is_faculty = assignment is not None

        if not is_pl and not is_faculty:
            raise HTTPException(
                status_code=403,
                detail="Not authorized"
            )

    await db.execute(
        delete(StudentMark).where(
            StudentMark.assessment_id == id
        )
    )

    for entry in data.marks:
        if (
            entry.marks_obtained is not None
            and entry.marks_obtained >= 0
        ):
            sm = StudentMark(
                id=str(uuid.uuid4()),
                assessment_id=id,
                student_id=entry.student_id,
                marks_obtained=entry.marks_obtained
            )
            db.add(sm)

    await db.commit()

    return {
        "message": "Marks saved successfully"
    }


@router.get("/report-card/{student_id}")
async def get_student_report_card(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Student).where(Student.id == student_id)
    )
    student = result.scalars().first()

    if not student:
        raise HTTPException(404, "Student not found")

    if (
        current_user.role == RoleEnum.STUDENT
        and student.user_id != current_user.id
    ):
        raise HTTPException(
            403,
            "You can only view your own report card"
        )

    if current_user.role == RoleEnum.PROGRAM_LEADER:
        result = await db.execute(
            select(ProgramLeaderAssignment).where(
                ProgramLeaderAssignment.user_id == current_user.id
            )
        )
        scope = result.scalars().first()

        if (
            not scope
            or scope.class_id != student.class_id
            or scope.section_id != student.section_id
        ):
            raise HTTPException(
                403,
                "Student is not in your assigned PL scope"
            )

    if current_user.role == RoleEnum.FACULTY:
        result = await db.execute(
            select(FacultyAssignment).where(
                FacultyAssignment.faculty_id == current_user.id,
                FacultyAssignment.section_id == student.section_id,
            )
        )
        assignment = result.scalars().first()

        if not assignment:
            raise HTTPException(
                403,
                "You do not teach this student's section"
            )

    result = await db.execute(
        select(StudentMark).where(
            StudentMark.student_id == student.id
        )
    )
    marks = result.scalars().all()

    report = []

    for m in marks:
        result = await db.execute(
            select(Assessment).where(
                Assessment.id == m.assessment_id
            )
        )
        assessment = result.scalars().first()

        if not assessment:
            continue

        result = await db.execute(
            select(Subject).where(
                Subject.id == assessment.subject_id
            )
        )
        subject = result.scalars().first()

        report.append({
            "id": m.id,
            "subject_name": (
                subject.name
                if subject
                else "Unknown"
            ),
            "subject_code": (
                subject.code
                if subject
                else "UNK"
            ),
            "assessment_name": assessment.name,
            "max_marks": assessment.max_marks,
            "obtained_marks": m.marks_obtained,
            "date": (
                assessment.date
                or str(assessment.created_at)
            )
        })

    result = await db.execute(
        select(CourseClass).where(
            CourseClass.id == student.class_id
        )
    )
    cls = result.scalars().first()

    result = await db.execute(
        select(Branch).where(
            Branch.id == student.branch_id
        )
    )
    br = result.scalars().first()

    result = await db.execute(
        select(Section).where(
            Section.id == student.section_id
        )
    )
    sec = result.scalars().first()

    return {
        "student": {
            "name": student.name,
            "enrollment_no": student.enrollment_no,
            "roll_number": student.roll_number,
            "class_name": cls.name if cls else "",
            "branch_name": br.name if br else "",
            "section_name": sec.name if sec else "",
            "year": student.year
        },
        "marks": sorted(
            report,
            key=lambda x: x["subject_name"]
        )
    }


@router.delete("/assessments/{id}")
async def delete_assessment(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Assessment).where(Assessment.id == id)
    )
    ass = result.scalars().first()

    if not ass:
        raise HTTPException(
            404,
            "Assessment not found"
        )

    if current_user.role in [
        RoleEnum.PROGRAM_LEADER,
        RoleEnum.FACULTY
    ]:
        result = await db.execute(
            select(ProgramLeaderAssignment).where(
                ProgramLeaderAssignment.user_id == current_user.id
            )
        )
        scope = result.scalars().first()

        is_pl = (
            current_user.role == RoleEnum.PROGRAM_LEADER
            and scope
            and scope.section_id == ass.section_id
        )

        result = await db.execute(
            select(FacultyAssignment).where(
                FacultyAssignment.faculty_id == current_user.id,
                FacultyAssignment.subject_id == ass.subject_id,
                FacultyAssignment.section_id == ass.section_id,
            )
        )
        assignment = result.scalars().first()

        is_faculty = assignment is not None

        if not is_pl and not is_faculty:
            raise HTTPException(
                status_code=403,
                detail="Not authorized"
            )

    await db.execute(
        delete(StudentMark).where(
            StudentMark.assessment_id == id
        )
    )

    await db.delete(ass)
    await db.commit()

    return {
        "message": "Assessment deleted successfully"
    }


@router.get("/assessments/{id}/export")
async def export_assessment_marks(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Assessment).where(Assessment.id == id)
    )
    ass = result.scalars().first()

    if not ass:
        raise HTTPException(
            404,
            "Assessment not found"
        )

    if current_user.role in [
        RoleEnum.PROGRAM_LEADER,
        RoleEnum.FACULTY
    ]:
        result = await db.execute(
            select(ProgramLeaderAssignment).where(
                ProgramLeaderAssignment.user_id == current_user.id
            )
        )
        scope = result.scalars().first()

        is_pl = (
            current_user.role == RoleEnum.PROGRAM_LEADER
            and scope
            and scope.section_id == ass.section_id
        )

        result = await db.execute(
            select(FacultyAssignment).where(
                FacultyAssignment.faculty_id == current_user.id,
                FacultyAssignment.subject_id == ass.subject_id,
                FacultyAssignment.section_id == ass.section_id,
            )
        )
        assignment = result.scalars().first()

        is_faculty = assignment is not None

        if not is_pl and not is_faculty:
            raise HTTPException(
                status_code=403,
                detail="Not authorized"
            )

    result = await db.execute(
        select(Student)
        .where(Student.section_id == ass.section_id)
        .order_by(Student.roll_number)
    )
    students = result.scalars().all()

    result = await db.execute(
        select(StudentMark).where(
            StudentMark.assessment_id == id
        )
    )
    existing_marks = {
        m.student_id: m
        for m in result.scalars().all()
    }

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Enrollment No",
        "Roll Number",
        "Student Name",
        "Max Marks",
        "Marks Obtained"
    ])

    for s in students:
        mark_record = existing_marks.get(s.id)

        marks_obtained = (
            mark_record.marks_obtained
            if mark_record
            else "N/A"
        )

        writer.writerow([
            s.enrollment_no,
            s.roll_number or "N/A",
            s.name,
            ass.max_marks,
            marks_obtained
        ])

    response = Response(
        content=output.getvalue(),
        media_type="text/csv"
    )

    response.headers["Content-Disposition"] = (
        f"attachment; "
        f"filename=marks_{ass.name.replace(' ', '_')}.csv"
    )

    return response
