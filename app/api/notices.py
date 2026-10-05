
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_
from typing import List, Optional
import uuid
import os
import shutil

from app.db.database import get_db
from app.models.models import (
    User,
    Notice,
    ProgramLeaderAssignment,
    RoleEnum,
    Student,
    FacultyAssignment,
)
from app.core.security import get_current_user

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("")
async def create_notice(
    title: str = Form(...),
    content: str = Form(...),
    audience: str = Form(...),
    file: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != RoleEnum.PROGRAM_LEADER:
        raise HTTPException(
            status_code=403,
            detail="Only Program Leaders can create notices."
        )

    result = await db.execute(
        select(ProgramLeaderAssignment).where(
            ProgramLeaderAssignment.user_id == current_user.id
        )
    )
    pl_scope = result.scalars().first()

    if not pl_scope:
        raise HTTPException(
            status_code=403,
            detail="No Program Leader assignment found."
        )

    attachment_url = None

    if file:
        file_ext = os.path.splitext(file.filename)[1]
        file_name = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, file_name)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        attachment_url = f"/uploads/{file_name}"

    notice = Notice(
        id=str(uuid.uuid4()),
        pl_id=current_user.id,
        title=title,
        content=content,
        audience=audience,
        class_id=pl_scope.class_id,
        year=pl_scope.year,
        branch_id=pl_scope.branch_id,
        section_id=pl_scope.section_id,
        attachment_url=attachment_url
    )

    db.add(notice)

    await db.commit()
    await db.refresh(notice)

    return {
        "message": "Notice published successfully",
        "notice_id": notice.id
    }


@router.get("")
async def get_notices(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role == RoleEnum.PROGRAM_LEADER:

        result = await db.execute(
            select(Notice)
            .where(Notice.pl_id == current_user.id)
            .order_by(Notice.created_at.desc())
        )

        notices = result.scalars().all()

    elif current_user.role == RoleEnum.STUDENT:

        result = await db.execute(
            select(Student).where(
                Student.user_id == current_user.id
            )
        )

        student = result.scalars().first()

        if not student:
            return []

        result = await db.execute(
            select(Notice)
            .where(
                Notice.class_id == student.class_id,
                Notice.year == student.year,
                Notice.branch_id == student.branch_id,
                Notice.section_id == student.section_id,
                Notice.audience.in_(["STUDENTS", "BOTH"])
            )
            .order_by(Notice.created_at.desc())
        )

        notices = result.scalars().all()

    elif current_user.role == RoleEnum.FACULTY:

        result = await db.execute(
            select(FacultyAssignment).where(
                FacultyAssignment.faculty_id == current_user.id
            )
        )

        faculty_assignments = result.scalars().all()

        if not faculty_assignments:
            return []

        conditions = []

        for fa in faculty_assignments:
            conditions.append(
                and_(
                    Notice.class_id == fa.class_id,
                    Notice.year == fa.year
                )
            )

        result = await db.execute(
            select(Notice)
            .where(
                or_(*conditions),
                Notice.audience.in_(["FACULTY", "BOTH"])
            )
            .order_by(Notice.created_at.desc())
        )

        notices = result.scalars().all()

    else:
        # Admin / Superadmin sees everything

        result = await db.execute(
            select(Notice)
            .order_by(Notice.created_at.desc())
        )

        notices = result.scalars().all()

    return notices


@router.delete("/{notice_id}")
async def delete_notice(
    notice_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(Notice).where(
            Notice.id == notice_id
        )
    )

    notice = result.scalars().first()

    if not notice:
        raise HTTPException(
            status_code=404,
            detail="Notice not found"
        )

    if (
        current_user.role != RoleEnum.SUPERADMIN
        and notice.pl_id != current_user.id
    ):
        raise HTTPException(
            status_code=403,
            detail="Not authorized to delete this notice"
        )

    await db.delete(notice)
    await db.commit()

    return {
        "message": "Notice deleted"
    }