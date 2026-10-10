
from fastapi import APIRouter, Depends, HTTPException, Form, Query, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from typing import List, Optional
from pydantic import BaseModel
import uuid
import sqlalchemy
import pandas as pd
import io

from app.db.database import get_db
from app.core.security import (
    get_admin_user,
    get_admin_or_pl_user,
    get_password_hash,
    get_superadmin_user,
)
from app.models.models import (
    User,
    Student,
    Subject,
    Section,
    FacultyAssignment,
    RoleEnum,
    AcademicYear,
    CourseClass,
    Branch,
    AttendanceRecord,
    AttendanceAuditLog,
    StudentMark,
    ProgramLeaderAssignment,
)


router = APIRouter()


class PasswordResetRequest(BaseModel):
    new_password: str


class FacultyCreate(BaseModel):
    name: str
    email: str
    employee_code: str
    department: str


class SubjectCreate(BaseModel):
    name: str
    code: str


async def enforce_pl_scope(
    db,
    user,
    class_id=None,
    year=None,
    branch_id=None,
    section_id=None,
):
    if user.role == RoleEnum.PROGRAM_LEADER:
        result = await db.execute(
            select(ProgramLeaderAssignment).where(
                ProgramLeaderAssignment.user_id == user.id
            )
        )
        scope = result.scalars().first()

        if not scope:
            raise HTTPException(
                status_code=403,
                detail="Program Leader scope not defined",
            )

        if class_id and scope.class_id != class_id:
            raise HTTPException(403, "Out of PL scope (class)")
        if year and scope.year != year:
            raise HTTPException(403, "Out of PL scope (year)")
        if branch_id and scope.branch_id != branch_id:
            raise HTTPException(403, "Out of PL scope (branch)")
        if section_id and scope.section_id != section_id:
            raise HTTPException(403, "Out of PL scope (section)")

        return scope

    return None


class PLCreate(BaseModel):
    user_id: str
    class_id: str
    year: str
    branch_id: str
    section_id: str


@router.post("/program-leaders")
async def assign_program_leader(
    data: PLCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    result = await db.execute(
        select(User).where(User.id == data.user_id)
    )
    user = result.scalars().first()

    if not user:
        raise HTTPException(404, "User not found")

    result = await db.execute(
        select(ProgramLeaderAssignment).where(
            ProgramLeaderAssignment.class_id == data.class_id,
            ProgramLeaderAssignment.year == data.year,
            ProgramLeaderAssignment.branch_id == data.branch_id,
            ProgramLeaderAssignment.section_id == data.section_id,
        )
    )
    existing_section_pl = result.scalars().first()

    if existing_section_pl and existing_section_pl.user_id != user.id:
        raise HTTPException(
            status_code=400,
            detail="A Program Leader is already assigned to this specific Class, Year, Branch, and Section.",
        )

    user.role = RoleEnum.PROGRAM_LEADER

    result = await db.execute(
        select(ProgramLeaderAssignment).where(
            ProgramLeaderAssignment.user_id == user.id
        )
    )
    existing = result.scalars().first()

    if existing:
        await db.delete(existing)

    pl = ProgramLeaderAssignment(
        id=str(uuid.uuid4()),
        user_id=user.id,
        class_id=data.class_id,
        year=data.year,
        branch_id=data.branch_id,
        section_id=data.section_id,
    )

    db.add(pl)
    await db.commit()

    return {"message": "Program Leader assigned successfully"}


@router.delete("/program-leaders/{id}")
async def remove_program_leader(
    id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    result = await db.execute(
        select(ProgramLeaderAssignment).where(
            ProgramLeaderAssignment.id == id
        )
    )
    pl = result.scalars().first()

    if not pl:
        raise HTTPException(404, "Program Leader assignment not found")

    result = await db.execute(
        select(User).where(User.id == pl.user_id)
    )
    user = result.scalars().first()

    if user:
        user.role = RoleEnum.FACULTY

    await db.delete(pl)
    await db.commit()

    return {"message": "Program Leader demoted successfully"}


@router.get("/program-leaders")
async def get_program_leaders(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    result = await db.execute(select(ProgramLeaderAssignment))
    pls = result.scalars().all()

    res = []

    for p in pls:
        result = await db.execute(
            select(User).where(User.id == p.user_id)
        )
        u = result.scalars().first()

        result = await db.execute(
            select(CourseClass).where(CourseClass.id == p.class_id)
        )
        c = result.scalars().first()

        result = await db.execute(
            select(Branch).where(Branch.id == p.branch_id)
        )
        b = result.scalars().first()

        result = await db.execute(
            select(Section).where(Section.id == p.section_id)
        )
        s = result.scalars().first()

        res.append({
            "id": p.id,
            "user_id": u.id,
            "name": u.name,
            "email": u.email,
            "class_name": c.name if c else "",
            "year": p.year,
            "branch_name": b.name if b else "",
            "section_name": s.name if s else "",
        })

    return res


class AssignmentCreate(BaseModel):
    academic_year_id: str
    class_id: str
    year: str
    branch_id: str
    section_id: str
    subject_id: str
    faculty_id: str


class BranchCreate(BaseModel):
    name: str
    code: Optional[str] = None


@router.post("/branches")
async def create_branch(
    data: BranchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    branch_name_lower = data.name.strip().lower()

    result = await db.execute(
        select(Branch).where(
            func.lower(Branch.name) == branch_name_lower
        )
    )
    existing = result.scalars().first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Branch already exists",
        )

    branch = Branch(
        id=str(uuid.uuid4()),
        name=branch_name_lower,
    )

    db.add(branch)
    await db.commit()
    await db.refresh(branch)

    return branch


class ClassCreate(BaseModel):
    name: str


@router.post("/classes")
async def create_class(
    data: ClassCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    name_clean = data.name.strip()

    result = await db.execute(
        select(CourseClass).where(
            func.lower(CourseClass.name) == name_clean.lower()
        )
    )
    existing = result.scalars().first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Class already exists",
        )

    course_class = CourseClass(
        id=str(uuid.uuid4()),
        name=name_clean,
    )

    db.add(course_class)
    await db.commit()
    await db.refresh(course_class)

    return course_class


@router.delete("/classes/{id}")
async def delete_class(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    result = await db.execute(
        select(CourseClass).where(CourseClass.id == id)
    )
    course_class = result.scalars().first()

    if not course_class:
        raise HTTPException(
            status_code=404,
            detail="Class not found",
        )

    await db.delete(course_class)
    await db.commit()

    return {"message": "Class deleted successfully"}


@router.delete("/subjects/{id}")
async def delete_subject(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    result = await db.execute(
        select(Subject).where(Subject.id == id)
    )
    subject = result.scalars().first()

    if not subject:
        raise HTTPException(
            status_code=404,
            detail="Subject not found",
        )

    await db.delete(subject)
    await db.commit()

    return {"message": "Subject deleted successfully"}


@router.delete("/branches/{id}")
async def delete_branch(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    result = await db.execute(
        select(Branch).where(Branch.id == id)
    )
    branch = result.scalars().first()

    if not branch:
        raise HTTPException(
            status_code=404,
            detail="Branch not found",
        )

    await db.delete(branch)
    await db.commit()

    return {"message": "Branch deleted successfully"}


class YearCreate(BaseModel):
    name: str


@router.post("/academic-years")
async def create_year(
    data: YearCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    name_clean = data.name.strip()

    result = await db.execute(
        select(AcademicYear).where(
            func.lower(AcademicYear.name) == name_clean.lower()
        )
    )
    existing = result.scalars().first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Year already exists",
        )

    year = AcademicYear(
        id=str(uuid.uuid4()),
        name=name_clean,
    )

    db.add(year)
    await db.commit()
    await db.refresh(year)

    return year


@router.delete("/academic-years/{id}")
async def delete_year(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    result = await db.execute(
        select(AcademicYear).where(AcademicYear.id == id)
    )
    year = result.scalars().first()

    if not year:
        raise HTTPException(
            status_code=404,
            detail="Year not found",
        )

    await db.delete(year)
    await db.commit()

    return {"message": "Year deleted successfully"}


@router.get("/options")
async def get_options(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_or_pl_user),
):
    scope = await enforce_pl_scope(db, admin)

    result = await db.execute(select(AcademicYear))
    academic_years = result.scalars().all()

    if not scope:
        result = await db.execute(select(CourseClass))
    else:
        result = await db.execute(
            select(CourseClass).where(
                CourseClass.id == scope.class_id
            )
        )
    classes = result.scalars().all()

    if not scope:
        result = await db.execute(select(Branch))
    else:
        result = await db.execute(
            select(Branch).where(
                Branch.id == scope.branch_id
            )
        )
    branches = result.scalars().all()

    if not scope:
        result = await db.execute(select(Section))
    else:
        result = await db.execute(
            select(Section).where(
                Section.id == scope.section_id
            )
        )
    sections = result.scalars().all()

    result = await db.execute(select(Subject))
    subjects = result.scalars().all()

    result = await db.execute(
        select(User).where(User.role == RoleEnum.FACULTY)
    )
    faculties = result.scalars().all()

    return {
        "academic_years": [
            {"id": x.id, "name": x.name}
            for x in academic_years
        ],
        "classes": [
            {"id": x.id, "name": x.name}
            for x in classes
        ],
        "branches": [
            {"id": x.id, "name": x.name}
            for x in branches
        ],
        "sections": [
            {"id": x.id, "name": x.name}
            for x in sections
        ],
        "subjects": [
            {"id": x.id, "name": x.name}
            for x in subjects
        ],
        "faculties": [
            {"id": x.id, "name": x.name, "email": x.email}
            for x in faculties
        ],
    }


@router.get("/assignments")
async def get_assignments(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_or_pl_user),
):
    scope = await enforce_pl_scope(db, admin)

    if scope:
        result = await db.execute(
            select(FacultyAssignment).where(
                FacultyAssignment.class_id == scope.class_id,
                FacultyAssignment.year == scope.year,
                FacultyAssignment.branch_id == scope.branch_id,
                FacultyAssignment.section_id == scope.section_id,
            )
        )
    else:
        result = await db.execute(
            select(FacultyAssignment)
        )

    assignments = result.scalars().all()
    res = []

    for a in assignments:
        result = await db.execute(
            select(CourseClass).where(CourseClass.id == a.class_id)
        )
        cls = result.scalars().first()

        result = await db.execute(
            select(Branch).where(Branch.id == a.branch_id)
        )
        br = result.scalars().first()

        result = await db.execute(
            select(Section).where(Section.id == a.section_id)
        )
        sec = result.scalars().first()

        result = await db.execute(
            select(Subject).where(Subject.id == a.subject_id)
        )
        sub = result.scalars().first()

        result = await db.execute(
            select(User).where(User.id == a.faculty_id)
        )
        fac = result.scalars().first()

        res.append({
            "id": a.id,
            "class_name": cls.name if cls else "",
            "year": a.year,
            "branch": br.name if br else "",
            "section": sec.name if sec else "",
            "subject": sub.name if sub else "",
            "faculty_name": fac.name if fac else "",
            "faculty_email": fac.email if fac else "",
            "academic_year": "2026-2027",
        })

    return res


@router.post("/assignments")
async def assign_faculty(
    data: AssignmentCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_or_pl_user),
):
    await enforce_pl_scope(
        db,
        admin,
        data.class_id,
        data.year,
        data.branch_id,
        data.section_id,
    )

    assign = FacultyAssignment(
        id=str(uuid.uuid4()),
        faculty_id=data.faculty_id,
        academic_year_id=data.academic_year_id,
        class_id=data.class_id,
        year=data.year,
        branch_id=data.branch_id,
        section_id=data.section_id,
        subject_id=data.subject_id,
    )

    db.add(assign)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="This faculty assignment already exists.",
        )

    return {"message": "Success"}


@router.delete("/assignments/{assignment_id}")
async def delete_assignment(
    assignment_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_or_pl_user),
):
    result = await db.execute(
        select(FacultyAssignment).where(
            FacultyAssignment.id == assignment_id
        )
    )
    ass = result.scalars().first()

    if not ass:
        raise HTTPException(404, "Not found")

    await enforce_pl_scope(
        db,
        admin,
        ass.class_id,
        ass.year,
        ass.branch_id,
        ass.section_id,
    )

    await db.delete(ass)
    await db.commit()

    return {"message": "Deleted"}


class StudentCreate(BaseModel):
    name: str
    email: str
    enrollment_no: str
    roll_number: Optional[str] = None
    class_id: str
    year: str
    branch_id: str
    section_id: str


@router.get("/students")
async def get_students(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    search: Optional[str] = None,
    class_id: Optional[str] = Query(None),
    year: Optional[str] = Query(None),
    branch_id: Optional[str] = Query(None),
    section_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_or_pl_user),
):
    scope = await enforce_pl_scope(db, admin)

    conditions = []

    if scope:
        conditions.extend([
            Student.class_id == scope.class_id,
            Student.year == scope.year,
            Student.branch_id == scope.branch_id,
            Student.section_id == scope.section_id,
        ])
    else:
        if class_id:
            conditions.append(Student.class_id == class_id)
        if year:
            conditions.append(Student.year == year)
        if branch_id:
            conditions.append(Student.branch_id == branch_id)
        if section_id:
            conditions.append(Student.section_id == section_id)

    if search and search.strip():
        conditions.append(
            (Student.name.ilike(f"%{search}%"))
            | (Student.enrollment_no.ilike(f"%{search}%"))
            | (Student.roll_number.ilike(f"%{search}%"))
        )

    result = await db.execute(
        select(func.count())
        .select_from(Student)
        .where(*conditions)
    )
    total = result.scalar() or 0

    result = await db.execute(
        select(Student)
        .where(*conditions)
        .order_by(Student.name)
        .offset(skip)
        .limit(limit)
    )
    students = result.scalars().all()

    res = []

    for s in students:
        result = await db.execute(
            select(CourseClass).where(CourseClass.id == s.class_id)
        )
        cls = result.scalars().first()

        result = await db.execute(
            select(Branch).where(Branch.id == s.branch_id)
        )
        br = result.scalars().first()

        result = await db.execute(
            select(Section).where(Section.id == s.section_id)
        )
        sec = result.scalars().first()

        res.append({
            "id": s.id,
            "user_id": s.user_id,
            "enrollment_no": s.enrollment_no,
            "roll_number": s.roll_number,
            "name": s.name,
            "email": s.email,
            "class_name": cls.name if cls else "",
            "year": s.year,
            "branch_name": br.name if br else "",
            "section_name": sec.name if sec else "",
            "class_id": s.class_id,
            "branch_id": s.branch_id,
            "section_id": s.section_id,
        })

    return {
        "total": total,
        "items": res,
        "skip": skip,
        "limit": limit,
    }


@router.post("/students")
async def create_student(
    data: StudentCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_or_pl_user),
):
    await enforce_pl_scope(
        db,
        admin,
        data.class_id,
        data.year,
        data.branch_id,
        data.section_id,
    )

    usr = User(
        id=str(uuid.uuid4()),
        email=data.email,
        name=data.name,
        hashed_password=get_password_hash(data.enrollment_no),
        role=RoleEnum.STUDENT,
    )

    db.add(usr)
    await db.flush()

    stu = Student(
        id=str(uuid.uuid4()),
        user_id=usr.id,
        name=data.name,
        email=data.email,
        enrollment_no=data.enrollment_no,
        roll_number=data.roll_number,
        class_id=data.class_id,
        year=data.year,
        branch_id=data.branch_id,
        section_id=data.section_id,
    )

    db.add(stu)

    try:
        await db.commit()
    except sqlalchemy.exc.IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Student already exists or Invalid Class/Year selected",
        )

    return {"message": "Success"}


class SectionCreate(BaseModel):
    name: str


@router.delete("/sections/{id}")
async def delete_section(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_admin_user),
):
    result = await db.execute(
        select(Section).where(Section.id == id)
    )
    section = result.scalars().first()

    if not section:
        raise HTTPException(
            status_code=404,
            detail="Section not found",
        )

    await db.delete(section)
    await db.commit()

    return {"message": "Section deleted successfully"}


@router.post("/sections")
async def create_section(
    data: SectionCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    sec = Section(
        id=str(uuid.uuid4()),
        name=data.name,
    )

    db.add(sec)
    await db.commit()
    await db.refresh(sec)

    return sec


@router.post("/faculty")
async def create_faculty(
    data: FacultyCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    fac = User(
        id=str(uuid.uuid4()),
        email=data.email,
        name=data.name,
        employee_code=data.employee_code,
        department=data.department,
        hashed_password=get_password_hash("password123"),
        role=RoleEnum.FACULTY,
    )

    db.add(fac)
    await db.commit()
    await db.refresh(fac)

    return fac


@router.post("/subjects")
async def create_subject(
    data: SubjectCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    sub = Subject(
        id=str(uuid.uuid4()),
        name=data.name,
        code=data.code,
    )

    db.add(sub)
    await db.commit()
    await db.refresh(sub)

    return sub


@router.get("/faculty")
async def get_faculty_list(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_or_pl_user),
):
    result = await db.execute(
        select(User).where(User.role == RoleEnum.FACULTY)
    )
    users = result.scalars().all()

    return [
        {
            "id": x.id,
            "name": x.name,
            "email": x.email,
            "employee_code": x.employee_code or "",
            "department": x.department or "",
        }
        for x in users
    ]


@router.get("/subjects")
async def get_subjects_list(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_or_pl_user),
):
    result = await db.execute(select(Subject))
    subjects = result.scalars().all()

    return [
        {
            "id": x.id,
            "name": x.name,
            "code": x.code,
        }
        for x in subjects
    ]


@router.get("/sections")
async def get_sections_list(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    result = await db.execute(select(Section))
    sections = result.scalars().all()

    return [
        {
            "id": x.id,
            "name": x.name,
        }
        for x in sections
    ]


class ValidStudentRow(BaseModel):
    name: str
    email: str
    enrollment_no: str
    roll_number: Optional[str]
    class_id: str
    year: str
    branch_id: str
    section_id: str


class ValidFacultyRow(BaseModel):
    name: str
    email: str
    employee_code: str
    department: str


class FacultyImportConfirm(BaseModel):
    faculty: List[ValidFacultyRow]


class ImportConfirm(BaseModel):
    students: List[ValidStudentRow]


@router.get("/students/import/template")
async def get_import_template(
    admin: User = Depends(get_admin_user),
):
    csv_data = (
        "Student Name,Email,Enrollment No,Roll No\n"
        "John Doe,john@test.com,EN2026001,101\n"
    )

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition":
                "attachment; filename=student_import_template.csv"
        },
    )


@router.post("/students/import/validate")
async def validate_import(
    file: UploadFile = File(...),
    class_id: str = Form(...),
    year: str = Form(...),
    branch_id: str = Form(...),
    section_id: str = Form(...),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    try:
        contents = await file.read()

        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))

    except Exception:
        raise HTTPException(400, "Invalid file format.")

    df = df.fillna("")

    result = await db.execute(select(User.email))
    existing_user_emails = set(result.scalars().all())

    result = await db.execute(select(Student.email))
    existing_student_emails = set(result.scalars().all())

    existing_emails = (
        existing_user_emails | existing_student_emails
    )

    result = await db.execute(select(Student.enrollment_no))
    existing_enrollments = set(result.scalars().all())

    valid_rows = []
    error_rows = []

    seen_emails_in_file = set()
    seen_enrollments_in_file = set()

    for idx, row in df.iterrows():
        row_num = idx + 2

        name = str(row.get("Student Name", "")).strip()
        email = str(row.get("Email", "")).strip()
        enr = str(row.get("Enrollment No", "")).strip()
        roll = str(row.get("Roll No", "")).strip()

        if not name or not email or not enr:
            error_rows.append({
                "row": row_num,
                "student": name or "Unknown",
                "error":
                    "Missing required fields "
                    "(Name, Email, Enrollment No)",
            })
            continue

        if email in existing_emails:
            error_rows.append({
                "row": row_num,
                "student": name,
                "error": "Email already exists in system",
            })
            continue

        if enr in existing_enrollments:
            error_rows.append({
                "row": row_num,
                "student": name,
                "error": f"Enrollment {enr} already exists",
            })
            continue

        if email in seen_emails_in_file:
            error_rows.append({
                "row": row_num,
                "student": name,
                "error": "Duplicate email inside file",
            })
            continue

        if enr in seen_enrollments_in_file:
            error_rows.append({
                "row": row_num,
                "student": name,
                "error": "Duplicate enrollment inside file",
            })
            continue

        seen_emails_in_file.add(email)
        seen_enrollments_in_file.add(enr)

        valid_rows.append({
            "name": name,
            "email": email,
            "enrollment_no": enr,
            "roll_number": roll if roll else None,
            "class_id": class_id,
            "year": year,
            "branch_id": branch_id,
            "section_id": section_id,
        })

    return {
        "total_rows": len(df),
        "valid_count": len(valid_rows),
        "error_count": len(error_rows),
        "valid_rows": valid_rows,
        "error_rows": error_rows,
    }


@router.post("/students/import")
async def confirm_import(
    data: ImportConfirm,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    added = 0

    for s in data.students:
        s_email = s.email.strip().lower() if s.email else ""
        s_name = s.name.strip().lower() if s.name else ""
        s_enr = (
            s.enrollment_no.strip().lower()
            if s.enrollment_no else ""
        )
        s_roll = (
            s.roll_number.strip().lower()
            if s.roll_number else ""
        )

        usr = User(
            id=str(uuid.uuid4()),
            email=s_email,
            name=s_name,
            hashed_password=get_password_hash(s_enr),
            role=RoleEnum.STUDENT,
        )

        db.add(usr)
        await db.flush()

        stu = Student(
            id=str(uuid.uuid4()),
            user_id=usr.id,
            name=s_name,
            email=s_email,
            enrollment_no=s_enr,
            roll_number=s_roll,
            class_id=s.class_id,
            year=s.year,
            branch_id=s.branch_id,
            section_id=s.section_id,
        )

        db.add(stu)
        added += 1

    await db.commit()

    return {
        "message":
            f"{added} students imported successfully."
    }


@router.put("/students/{student_id}")
async def update_student(
    student_id: str,
    data: StudentCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_or_pl_user),
):
    await enforce_pl_scope(
        db,
        admin,
        data.class_id,
        data.year,
        data.branch_id,
        data.section_id,
    )

    result = await db.execute(
        select(Student).where(Student.id == student_id)
    )
    stu = result.scalars().first()

    if not stu:
        raise HTTPException(
            status_code=404,
            detail="Student not found",
        )

    await enforce_pl_scope(
        db,
        admin,
        stu.class_id,
        stu.year,
        stu.branch_id,
        stu.section_id,
    )

    stu.name = data.name
    stu.email = data.email
    stu.roll_number = data.roll_number
    stu.class_id = data.class_id
    stu.year = data.year
    stu.branch_id = data.branch_id
    stu.section_id = data.section_id

    result = await db.execute(
        select(User).where(User.id == stu.user_id)
    )
    usr = result.scalars().first()

    if usr:
        usr.name = data.name
        usr.email = data.email

    await db.commit()

    return {
        "message": "Student updated successfully"
    }


@router.post("/users/{user_id}/reset-password")
async def reset_user_password(
    user_id: str,
    data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_admin_or_pl_user),
):
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    if current_user.role == RoleEnum.PROGRAM_LEADER:
        result = await db.execute(
            select(Student).where(Student.user_id == user_id)
        )
        student = result.scalars().first()

        if not student:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Program Leaders can only reset "
                    "passwords for students."
                ),
            )

        await enforce_pl_scope(
            db,
            current_user,
            student.class_id,
            student.year,
            student.branch_id,
            student.section_id,
        )

    user.hashed_password = get_password_hash(
        data.new_password
    )

    await db.commit()

    return {
        "message": "Password reset successfully"
    }


@router.get("/faculty/import/template")
async def get_fac_import_template(
    admin: User = Depends(get_admin_user),
):
    csv_data = (
        "Faculty Name,Email,Employee Code,Department\n"
        "Jane Smith,jane@test.com,EMP001,Computer Science\n"
    )

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition":
                "attachment; filename=faculty_import_template.csv"
        },
    )


@router.post("/faculty/import/validate")
async def validate_fac_import(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    try:
        contents = await file.read()

        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))

    except Exception:
        raise HTTPException(400, "Invalid file format.")

    df = df.fillna("")

    result = await db.execute(select(User.email))
    existing_user_emails = set(result.scalars().all())

    result = await db.execute(select(Student.email))
    existing_student_emails = set(result.scalars().all())

    existing_emails = (
        existing_user_emails | existing_student_emails
    )

    result = await db.execute(
        select(User.employee_code).where(
            User.employee_code.isnot(None)
        )
    )
    existing_codes = set(result.scalars().all())

    valid_rows = []
    error_rows = []

    seen_emails = set()
    seen_codes = set()

    for idx, row in df.iterrows():
        row_num = idx + 2

        name = str(row.get("Faculty Name", "")).strip()
        email = str(row.get("Email", "")).strip()
        code = str(row.get("Employee Code", "")).strip()
        dept = str(row.get("Department", "")).strip()

        if not name or not email or not code or not dept:
            error_rows.append({
                "row": row_num,
                "name": name or "Unknown",
                "error": "Missing required fields",
            })
            continue

        if email in existing_emails:
            error_rows.append({
                "row": row_num,
                "name": name,
                "error": "Email already exists in system",
            })
            continue

        if code in existing_codes:
            error_rows.append({
                "row": row_num,
                "name": name,
                "error":
                    f"Employee Code {code} already exists",
            })
            continue

        if email in seen_emails:
            error_rows.append({
                "row": row_num,
                "name": name,
                "error": "Duplicate email inside file",
            })
            continue

        if code in seen_codes:
            error_rows.append({
                "row": row_num,
                "name": name,
                "error":
                    "Duplicate employee code inside file",
            })
            continue

        seen_emails.add(email)
        seen_codes.add(code)

        valid_rows.append({
            "name": name,
            "email": email,
            "employee_code": code,
            "department": dept,
        })

    return {
        "valid_count": len(valid_rows),
        "error_count": len(error_rows),
        "valid_rows": valid_rows,
        "error_rows": error_rows,
    }


@router.post("/faculty/import")
async def confirm_fac_import(
    data: FacultyImportConfirm,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    added = 0

    for f_row in data.faculty:
        fac = User(
            id=str(uuid.uuid4()),
            email=f_row.email,
            name=f_row.name,
            employee_code=f_row.employee_code,
            department=f_row.department,
            hashed_password=get_password_hash("password123"),
            role=RoleEnum.FACULTY,
        )

        db.add(fac)
        added += 1

    await db.commit()

    return {
        "message":
            f"Successfully imported {added} faculty members"
    }


@router.delete("/faculty/{faculty_id}")
async def delete_faculty(
    faculty_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    result = await db.execute(
        select(User).where(
            User.id == faculty_id,
            User.role == RoleEnum.FACULTY,
        )
    )
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            404,
            "Faculty not found",
        )

    await db.execute(
        delete(FacultyAssignment).where(
            FacultyAssignment.faculty_id == faculty_id
        )
    )

    await db.delete(user)
    await db.commit()

    return {
        "message": "Faculty deleted successfully"
    }


@router.delete("/students/{student_id}")
async def delete_student(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_or_pl_user),
):
    result = await db.execute(
        select(Student).where(Student.id == student_id)
    )
    stu = result.scalars().first()

    if not stu:
        raise HTTPException(
            status_code=404,
            detail="Student not found",
        )

    await enforce_pl_scope(
        db,
        admin,
        stu.class_id,
        stu.year,
        stu.branch_id,
        stu.section_id,
    )

    result = await db.execute(
        select(User).where(User.id == stu.user_id)
    )
    usr = result.scalars().first()

    await db.execute(
        delete(AttendanceRecord).where(
            AttendanceRecord.student_id == stu.id
        )
    )

    await db.execute(
        delete(AttendanceAuditLog).where(
            AttendanceAuditLog.student_id == stu.id
        )
    )

    await db.delete(stu)

    if usr:
        await db.delete(usr)

    await db.commit()

    return {
        "message": "Student deleted"
    }


class AdminCreate(BaseModel):
    name: str
    email: str
    password: str


@router.get("/superadmin/admins")
async def get_admins(
    db: AsyncSession = Depends(get_db),
    superadmin: User = Depends(get_superadmin_user),
):
    result = await db.execute(
        select(User).where(
            User.role == RoleEnum.ADMIN
        )
    )

    return result.scalars().all()


@router.post("/superadmin/admins")
async def create_admin(
    data: AdminCreate,
    db: AsyncSession = Depends(get_db),
    superadmin: User = Depends(get_superadmin_user),
):
    result = await db.execute(
        select(User).where(
            User.email == data.email
        )
    )
    existing = result.scalars().first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="User with this email already exists",
        )

    new_admin = User(
        id=str(uuid.uuid4()),
        name=data.name,
        email=data.email,
        hashed_password=get_password_hash(data.password),
        role=RoleEnum.ADMIN,
    )

    db.add(new_admin)
    await db.commit()
    await db.refresh(new_admin)

    return new_admin


@router.delete("/superadmin/admins/{id}")
async def delete_admin(
    id: str,
    db: AsyncSession = Depends(get_db),
    superadmin: User = Depends(get_superadmin_user),
):
    result = await db.execute(
        select(User).where(
            User.id == id,
            User.role == RoleEnum.ADMIN,
        )
    )
    admin = result.scalars().first()

    if not admin:
        raise HTTPException(
            status_code=404,
            detail="Admin not found",
        )

    await db.delete(admin)
    await db.commit()

    return {
        "message": "Admin deleted successfully"
    }


class RoleUpdate(BaseModel):
    role: str


@router.put("/superadmin/users/{id}/role")
async def update_user_role(
    id: str,
    data: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    superadmin: User = Depends(get_superadmin_user),
):
    result = await db.execute(
        select(User).where(User.id == id)
    )
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    if data.role not in [
        RoleEnum.ADMIN,
        RoleEnum.FACULTY,
    ]:
        raise HTTPException(
            status_code=400,
            detail="Invalid role assignment",
        )

    user.role = data.role
    await db.commit()

    return {
        "message":
            f"User role updated to {data.role}"
    }


@router.get("/superadmin/faculty-list")
async def get_all_faculty_for_promotion(
    db: AsyncSession = Depends(get_db),
    superadmin: User = Depends(get_superadmin_user),
):
    result = await db.execute(
        select(User).where(
            User.role.in_([
                RoleEnum.FACULTY,
                RoleEnum.ADMIN,
            ])
        )
    )

    users = result.scalars().all()

    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role,
        }
        for u in users
    ]


@router.post("/superadmin/users/{id}/reset-password")
async def superadmin_reset_password(
    id: str,
    data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
    superadmin: User = Depends(get_superadmin_user),
):
    result = await db.execute(
        select(User).where(User.id == id)
    )
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    user.hashed_password = get_password_hash(
        data.new_password
    )

    await db.commit()

    return {
        "message":
            f"Password reset successfully for {user.name}"
    }


class AllocationFilter(BaseModel):
    class_id: str
    year: str
    branch_id: str
    section_id: str


class BulkDeleteRequest(BaseModel):
    student_ids: List[str]
    allocation: AllocationFilter


@router.post("/students/bulk-delete")
async def bulk_delete_students(
    data: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    alloc = data.allocation

    if (
        not alloc.class_id
        or not alloc.year
        or not alloc.branch_id
        or not alloc.section_id
    ):
        raise HTTPException(
            400,
            "Academic Allocation must be completely specified to execute a bulk deletion.",
        )

    result = await db.execute(
        select(Student).where(
            Student.id.in_(data.student_ids)
        )
    )
    students = result.scalars().all()

    if not students:
        raise HTTPException(
            404,
            "No students found matching the provided IDs.",
        )

    user_ids_to_delete = []

    for s in students:
        if (
            s.class_id != alloc.class_id
            or s.year != alloc.year
            or s.branch_id != alloc.branch_id
            or s.section_id != alloc.section_id
        ):
            raise HTTPException(
                403,
                f"Authorization violation: Student "
                f"{s.name} ({s.enrollment_no}) does not "
                f"belong to the selected Academic Allocation. "
                f"Bulk deletion aborted for safety.",
            )

        if s.user_id:
            user_ids_to_delete.append(s.user_id)

    try:
        await db.execute(
            delete(AttendanceRecord).where(
                AttendanceRecord.student_id.in_(
                    data.student_ids
                )
            )
        )

        await db.execute(
            delete(StudentMark).where(
                StudentMark.student_id.in_(
                    data.student_ids
                )
            )
        )

        await db.execute(
            delete(Student).where(
                Student.id.in_(data.student_ids)
            )
        )

        if user_ids_to_delete:
            await db.execute(
                delete(User).where(
                    User.id.in_(user_ids_to_delete)
                )
            )

        await db.commit()

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            500,
            f"Database transaction failed: {str(e)}",
        )

    return {
        "message":
            f"{len(students)} students deleted successfully."
    }
