# from app.models.models import ProgramLeaderAssignment
# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session
# from typing import List
# from pydantic import BaseModel
# from datetime import datetime
# from app.db.database import get_db
# from app.core.security import get_current_user
# from app.models.models import User, AttendanceSession, AttendanceRecord, FacultyAssignment, RoleEnum, AttendanceStatus, AttendanceAuditLog, CourseClass, Branch, Section, Subject
# import uuid
# import sqlalchemy
#
# router = APIRouter()
#
# class RecordCreate(BaseModel):
#     student_id: str
#     status: AttendanceStatus
#
# class SessionCreate(BaseModel):
#     section_id: str
#     subject_id: str
#     date: str
#     start_time: str
#     end_time: str
#     records: List[RecordCreate]
#
# @router.get("/my-assignments")
# def get_my_assignments(strict_faculty: bool = False, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
#     from app.models.models import ProgramLeaderAssignment
#     if current_user.role not in [RoleEnum.FACULTY, RoleEnum.PROGRAM_LEADER]:
#         raise HTTPException(status_code=403, detail="Not authorized to access assignments")
#
#     if strict_faculty:
#         assignments = db.query(FacultyAssignment).filter_by(faculty_id=current_user.id).all()
#     elif current_user.role == RoleEnum.PROGRAM_LEADER:
#         scope = db.query(ProgramLeaderAssignment).filter_by(user_id=current_user.id).first()
#
#         # Get PL scope assignments
#         pl_assignments = []
#         if scope:
#             pl_assignments = db.query(FacultyAssignment).filter_by(
#                 class_id=scope.class_id,
#                 year=scope.year,
#                 branch_id=scope.branch_id,
#                 section_id=scope.section_id
#             ).all()
#
#         # Get their actual teaching assignments (which might be outside their PL scope)
#         faculty_assignments = db.query(FacultyAssignment).filter_by(faculty_id=current_user.id).all()
#
#         # Combine them and remove duplicates based on unique sections/subjects
#         combined = {f"{a.section_id}|{a.subject_id}": a for a in pl_assignments + faculty_assignments}
#         assignments = list(combined.values())
#     else:
#         assignments = db.query(FacultyAssignment).filter_by(faculty_id=current_user.id).all()
#     res = []
#     for a in assignments:
#         cls = db.query(CourseClass).filter_by(id=a.class_id).first()
#         br = db.query(Branch).filter_by(id=a.branch_id).first()
#         sec = db.query(Section).filter_by(id=a.section_id).first()
#         sub = db.query(Subject).filter_by(id=a.subject_id).first()
#         if cls and br and sec and sub:
#             res.append({
#                 "class_id": cls.id,
#                 "class_name": cls.name,
#                 "year": a.year,
#                 "branch_id": br.id,
#                 "branch_name": br.name,
#                 "section_id": sec.id,
#                 "section_name": sec.name,
#                 "subject_id": sub.id,
#                 "subject_name": sub.name,
#                 "faculty_id": a.faculty_id
#             })
#     return res
#
# @router.post("/sessions")
# def create_session(data: SessionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
#     if data.end_time <= data.start_time:
#         raise HTTPException(status_code=400, detail="Time To must be strictly after Time From")
#     parsed_date = datetime.strptime(data.date.split('T')[0], '%Y-%m-%d')
#     # 1. Isolation check
#     if current_user.role == RoleEnum.PROGRAM_LEADER:
#         scope = db.query(ProgramLeaderAssignment).filter_by(user_id=current_user.id).first()
#         if not scope:
#             raise HTTPException(status_code=403, detail="PL scope not found")
#         # Find the cohort this section/subject belongs to
#         cohort_check = db.query(FacultyAssignment).filter_by(
#             section_id=data.section_id,
#             subject_id=data.subject_id
#         ).first()
#         if not cohort_check:
#             raise HTTPException(status_code=400, detail="Invalid section or subject combination")
#         if (cohort_check.class_id != scope.class_id or
#             cohort_check.year != scope.year or
#             cohort_check.branch_id != scope.branch_id or
#             cohort_check.section_id != scope.section_id):
#             raise HTTPException(status_code=403, detail="Out of PL scope (Class/Branch/Year/Section mismatch)")
#     elif current_user.role == RoleEnum.FACULTY:
#         assignment = db.query(FacultyAssignment).filter_by(
#             faculty_id=current_user.id,
#             section_id=data.section_id,
#             subject_id=data.subject_id
#         ).first()
#         if not assignment:
#             raise HTTPException(status_code=403, detail="Unauthorized to mark attendance for this section/subject combination.")
#
#     # 2. Check for duplicate session overlap
#     target_assignment = db.query(FacultyAssignment).filter_by(
#         section_id=data.section_id,
#         subject_id=data.subject_id
#     ).first()
#
#     if target_assignment:
#         overlapping_session = db.query(AttendanceSession).join(
#             FacultyAssignment,
#             (AttendanceSession.faculty_id == FacultyAssignment.faculty_id) &
#             (AttendanceSession.section_id == FacultyAssignment.section_id) &
#             (AttendanceSession.subject_id == FacultyAssignment.subject_id)
#         ).filter(
#             FacultyAssignment.class_id == target_assignment.class_id,
#             FacultyAssignment.branch_id == target_assignment.branch_id,
#             FacultyAssignment.section_id == target_assignment.section_id,
#             AttendanceSession.date == parsed_date,
#             AttendanceSession.start_time < data.end_time,
#             AttendanceSession.end_time > data.start_time
#         ).first()
#
#         if overlapping_session:
#             raise HTTPException(status_code=400, detail=f"Overlapping session detected ({overlapping_session.start_time} - {overlapping_session.end_time}) for this Class/Branch/Section.")
#     else:
#         existing_session = db.query(AttendanceSession).filter_by(
#             section_id=data.section_id,
#             date=parsed_date,
#             start_time=data.start_time,
#             end_time=data.end_time
#         ).first()
#         if existing_session:
#             raise HTTPException(status_code=400, detail="Attendance session already exists for this exact time slot.")
#
#     new_session = AttendanceSession(
#         id=str(uuid.uuid4()),
#         section_id=data.section_id,
#         subject_id=data.subject_id,
#         faculty_id=current_user.id,
#         date=parsed_date,
#         start_time=data.start_time,
#         end_time=data.end_time
#     )
#     db.add(new_session)
#
#     for r in data.records:
#         rec = AttendanceRecord(
#             id=str(uuid.uuid4()),
#             session_id=new_session.id,
#             student_id=r.student_id,
#             status=r.status
#         )
#         db.add(rec)
#
#     try:
#         db.commit()
#     except sqlalchemy.exc.IntegrityError:
#         db.rollback()
#         raise HTTPException(status_code=400, detail="Database integrity error. Check duplicates.")
#
#     return {"message": "Attendance created", "session_id": new_session.id}
#
# @router.get("/students/{section_id}")
# def get_students(section_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
#     from app.models.models import Student
#     if current_user.role == RoleEnum.PROGRAM_LEADER:
#         scope = db.query(ProgramLeaderAssignment).filter_by(user_id=current_user.id).first()
#         if not scope or scope.section_id != section_id:
#             raise HTTPException(status_code=403, detail="Out of PL scope")
#     elif current_user.role == RoleEnum.FACULTY:
#         assignment = db.query(FacultyAssignment).filter_by(faculty_id=current_user.id, section_id=section_id).first()
#         if not assignment:
#             raise HTTPException(status_code=403, detail="Unauthorized section access")
#     return db.query(Student).filter_by(section_id=section_id).all()
#
# @router.get("/report/options")
# def get_report_options(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
#     from app.models.models import CourseClass, Branch, Section, Subject
#
#     if current_user.role == RoleEnum.PROGRAM_LEADER:
#         scope = db.query(ProgramLeaderAssignment).filter_by(user_id=current_user.id).first()
#         if not scope:
#             assignments = []
#         else:
#             assignments = db.query(FacultyAssignment).filter_by(class_id=scope.class_id, year=scope.year, branch_id=scope.branch_id, section_id=scope.section_id).all()
#     elif current_user.role == RoleEnum.FACULTY:
#         assignments = db.query(FacultyAssignment).filter_by(faculty_id=current_user.id).all()
#     else:
#         assignments = db.query(FacultyAssignment).all()
#
#     res = []
#     for a in assignments:
#         cls = db.query(CourseClass).filter_by(id=a.class_id).first()
#         br = db.query(Branch).filter_by(id=a.branch_id).first()
#         sec = db.query(Section).filter_by(id=a.section_id).first()
#         sub = db.query(Subject).filter_by(id=a.subject_id).first()
#         if cls and br and sec and sub:
#             res.append({
#                 "class_id": cls.id, "class_name": cls.name,
#                 "year": a.year,
#                 "branch_id": br.id, "branch_name": br.name,
#                 "section_id": sec.id, "section_name": sec.name,
#                 "subject_id": sub.id, "subject_name": sub.name
#             })
#     return res
#
# @router.get("/report/subject")
# def get_subject_report(section_id: str, subject_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
#     from app.models.models import Student
#
#     if current_user.role == RoleEnum.PROGRAM_LEADER:
#         scope = db.query(ProgramLeaderAssignment).filter_by(user_id=current_user.id).first()
#         if not scope or scope.section_id != section_id:
#             raise HTTPException(status_code=403, detail="Out of PL scope")
#         # For PL, they just need to match the section. (Ideally match full scope, but section_id limits it here).
#         cohort_check = db.query(FacultyAssignment).filter_by(section_id=section_id, subject_id=subject_id).first()
#         if not cohort_check or cohort_check.class_id != scope.class_id:
#             raise HTTPException(status_code=403, detail="Out of PL scope")
#     elif current_user.role == RoleEnum.FACULTY:
#         assignment = db.query(FacultyAssignment).filter_by(faculty_id=current_user.id, section_id=section_id, subject_id=subject_id).first()
#         if not assignment:
#             raise HTTPException(status_code=403, detail="Unauthorized to view reports for this section/subject.")
#
#     students = db.query(Student).filter_by(section_id=section_id).all()
#     sessions = db.query(AttendanceSession).filter_by(section_id=section_id, subject_id=subject_id).all()
#     session_ids = [s.id for s in sessions]
#     total_sessions = len(session_ids)
#
#     stats = {s.id: {"present": 0, "absent": 0} for s in students}
#
#     if total_sessions > 0:
#         records = db.query(AttendanceRecord).filter(AttendanceRecord.session_id.in_(session_ids)).all()
#         for r in records:
#             if r.student_id in stats:
#                 if r.status == AttendanceStatus.PRESENT:
#                     stats[r.student_id]["present"] += 1
#                 else:
#                     stats[r.student_id]["absent"] += 1
#
#     report = []
#     for s in students:
#         attended = stats[s.id]["present"]
#         percentage = (attended / total_sessions * 100) if total_sessions > 0 else 0
#         report.append({
#             "student_id": s.id,
#             "name": s.name,
#             "roll_number": s.roll_number,
#             "total_sessions": total_sessions,
#             "attended": attended,
#             "percentage": round(percentage, 2)
#         })
#
#     # Sort by roll number optionally, but let's just return
#     return sorted(report, key=lambda x: x['name'])
#
# from datetime import datetime
#
# def calculate_lectures(start_time_str: str, end_time_str: str) -> int:
#     try:
#         fmt = "%H:%M"
#         t1 = datetime.strptime(start_time_str, fmt)
#         t2 = datetime.strptime(end_time_str, fmt)
#         diff_mins = (t2 - t1).total_seconds() / 60
#         return 2 if diff_mins > 60 else 1
#     except:
#         return 1
#
# @router.get("/my-attendance")
# def get_my_attendance(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
#     from app.models.models import Student, AttendanceRecord, AttendanceSession, Subject
#
#     if current_user.role != RoleEnum.STUDENT:
#         raise HTTPException(status_code=403, detail="Only students can access this endpoint")
#
#     student = db.query(Student).filter_by(user_id=current_user.id).first()
#     if not student:
#         raise HTTPException(status_code=404, detail="Student profile not found")
#
#     records = db.query(AttendanceRecord).filter_by(student_id=student.id).all()
#     session_ids = [r.session_id for r in records]
#     sessions = db.query(AttendanceSession).filter(AttendanceSession.id.in_(session_ids)).all()
#     sessions_map = {s.id: s for s in sessions}
#
#     subjects = {s.id: s.name for s in db.query(Subject).all()}
#     faculties = {f.id: f.name for f in db.query(User).filter_by(role=RoleEnum.FACULTY).all()}
#
#     subject_stats = {}
#     history = []
#
#     overall_total = 0
#     overall_present = 0
#
#     for r in records:
#         sess = sessions_map.get(r.session_id)
#         if not sess: continue
#
#         subj_name = subjects.get(sess.subject_id, "Unknown Subject")
#         fac_name = faculties.get(sess.faculty_id, "Unknown Faculty")
#         lec_count = calculate_lectures(sess.start_time, sess.end_time)
#
#         if sess.subject_id not in subject_stats:
#             subject_stats[sess.subject_id] = {
#                 "subject_id": sess.subject_id, "subject_name": subj_name,
#                 "total": 0, "present": 0, "absent": 0
#             }
#
#         subject_stats[sess.subject_id]["total"] += lec_count
#         overall_total += lec_count
#
#         if r.status.upper() == "PRESENT":
#             subject_stats[sess.subject_id]["present"] += lec_count
#             overall_present += lec_count
#         else:
#             subject_stats[sess.subject_id]["absent"] += lec_count
#
#         history.append({
#             "id": r.id, "date": str(sess.date).split(" ")[0], "subject": subj_name, "faculty": fac_name,
#             "time": f"{sess.start_time} - {sess.end_time}", "lectures": lec_count, "status": r.status.title()
#         })
#
#     for sub_id, stats in subject_stats.items():
#         stats["percentage"] = round((stats["present"] / stats["total"] * 100), 2) if stats["total"] > 0 else 0
#         stats["status"] = "Good" if stats["percentage"] >= 75 else "Defaulter"
#
#     overall_percentage = round((overall_present / overall_total * 100), 2) if overall_total > 0 else 0
#
#     # Generate daily trend data (last 14 active days)
#     daily = {}
#     for h in history:
#         d = h["date"]
#         if d not in daily:
#             daily[d] = {"present": 0, "absent": 0, "total": 0}
#         daily[d]["total"] += h["lectures"]
#         if h["status"].upper() == "PRESENT": daily[d]["present"] += h["lectures"]
#         else: daily[d]["absent"] += h["lectures"]
#
#     trend = [{"date": k, "percentage": round(v["present"]/v["total"]*100) if v["total"]>0 else 0} for k, v in sorted(daily.items())[-14:]]
#
#     return {
#         "overall": {
#             "percentage": overall_percentage, "total_lectures": overall_total,
#             "present_lectures": overall_present, "absent_lectures": overall_total - overall_present,
#             "is_defaulter": overall_percentage < 75 and overall_total > 0
#         },
#         "subject_wise": list(subject_stats.values()),
#         "history": sorted(history, key=lambda x: x['date'], reverse=True),
#         "trend": trend
#     }
#
# @router.put("/sessions/{session_id}")
# def update_session(session_id: str, data: SessionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
#     if data.end_time <= data.start_time:
#         raise HTTPException(status_code=400, detail="Time To must be strictly after Time From")
#     session = db.query(AttendanceSession).filter_by(id=session_id).first()
#     if not session:
#         raise HTTPException(status_code=404, detail="Session not found")
#
#     # Check authorization
#     if current_user.role == RoleEnum.PROGRAM_LEADER:
#         scope = db.query(ProgramLeaderAssignment).filter_by(user_id=current_user.id).first()
#         if not scope:
#             raise HTTPException(status_code=403, detail="PL scope not found")
#         cohort_check = db.query(FacultyAssignment).filter_by(
#             section_id=data.section_id,
#             subject_id=data.subject_id
#         ).first()
#         if not cohort_check:
#             raise HTTPException(status_code=400, detail="Invalid section/subject")
#         if (cohort_check.class_id != scope.class_id or
#             cohort_check.year != scope.year or
#             cohort_check.branch_id != scope.branch_id or
#             cohort_check.section_id != scope.section_id):
#             raise HTTPException(status_code=403, detail="Out of PL scope (Class/Branch/Year/Section mismatch)")
#     elif current_user.role == RoleEnum.FACULTY:
#         assignment = db.query(FacultyAssignment).filter_by(
#             faculty_id=current_user.id,
#             section_id=data.section_id,
#             subject_id=data.subject_id
#         ).first()
#         if not assignment:
#             raise HTTPException(status_code=403, detail="Unauthorized to mark attendance for this section/subject combination.")
#     elif current_user.role != RoleEnum.ADMIN:
#         raise HTTPException(status_code=403, detail="Not authorized")
#
#     parsed_date = datetime.strptime(data.date.split('T')[0], '%Y-%m-%d')
#
#     target_assignment = db.query(FacultyAssignment).filter_by(
#         section_id=data.section_id,
#         subject_id=data.subject_id
#     ).first()
#
#     if target_assignment:
#         overlapping_session = db.query(AttendanceSession).join(
#             FacultyAssignment,
#             (AttendanceSession.faculty_id == FacultyAssignment.faculty_id) &
#             (AttendanceSession.section_id == FacultyAssignment.section_id) &
#             (AttendanceSession.subject_id == FacultyAssignment.subject_id)
#         ).filter(
#             FacultyAssignment.class_id == target_assignment.class_id,
#             FacultyAssignment.branch_id == target_assignment.branch_id,
#             FacultyAssignment.section_id == target_assignment.section_id,
#             AttendanceSession.date == parsed_date,
#             AttendanceSession.start_time < data.end_time,
#             AttendanceSession.end_time > data.start_time,
#             AttendanceSession.id != session_id
#         ).first()
#
#         if overlapping_session:
#             raise HTTPException(status_code=400, detail=f"Overlapping session detected ({overlapping_session.start_time} - {overlapping_session.end_time}) for this Class/Branch/Section.")
#
#     session.date = parsed_date
#     session.start_time = data.start_time
#     session.end_time = data.end_time
#
#
#     # Update records
#     for rec_data in data.records:
#         rec = db.query(AttendanceRecord).filter_by(session_id=session_id, student_id=rec_data.student_id).first()
#         if rec:
#             if rec.status != rec_data.status:
#                 if current_user.role == RoleEnum.PROGRAM_LEADER:
#                     audit = AttendanceAuditLog(
#                         id=str(uuid.uuid4()),
#                         session_id=session_id,
#                         student_id=rec_data.student_id,
#                         changed_by=current_user.id,
#                         previous_status=rec.status,
#                         new_status=rec_data.status
#                     )
#                     db.add(audit)
#                 rec.status = rec_data.status
#         else:
#             new_rec = AttendanceRecord(
#                 id=str(uuid.uuid4()),
#                 session_id=session_id,
#                 student_id=rec_data.student_id,
#                 status=rec_data.status
#             )
#             db.add(new_rec)
#
#     db.commit()
#     return {"message": "Attendance updated successfully"}
#
# @router.get("/sessions/date")
# def get_sessions_by_date(section_id: str, subject_id: str, date: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
#     from datetime import datetime
#     # Use string matching (LIKE) to completely bypass SQLite/Postgres datetime microsecond mismatch issues
#     sessions = db.query(AttendanceSession).filter(
#         AttendanceSession.section_id == section_id,
#         AttendanceSession.subject_id == subject_id,
#         AttendanceSession.date.like(f"{date}%")
#     ).all()
#     res = []
#     for s in sessions:
#         records = db.query(AttendanceRecord).filter_by(session_id=s.id).all()
#         res.append({
#             "id": s.id,
#             "start_time": s.start_time,
#             "end_time": s.end_time,
#             "records": [{"student_id": r.student_id, "status": r.status} for r in records]
#         })
#     return res
#
# @router.get("/audit-logs")
# def get_audit_logs(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
#     from app.models.models import Student
#     if current_user.role not in [RoleEnum.ADMIN, RoleEnum.PROGRAM_LEADER]:
#         raise HTTPException(status_code=403, detail="Not authorized to view audit logs")
#
#     logs = db.query(AttendanceAuditLog).order_by(AttendanceAuditLog.created_at.desc()).limit(100).all()
#     res = []
#     for log in logs:
#         student = db.query(Student).filter_by(id=log.student_id).first()
#         changer = db.query(User).filter_by(id=log.changed_by).first()
#         session = db.query(AttendanceSession).filter_by(id=log.session_id).first()
#
#         res.append({
#             "id": log.id,
#             "student_name": student.name if student else "Unknown",
#             "roll_number": student.roll_number if student else "-",
#             "changed_by": changer.name if changer else "Unknown",
#             "changer_role": changer.role if changer else "Unknown",
#             "previous_status": log.previous_status,
#             "new_status": log.new_status,
#             "timestamp": log.created_at.isoformat() if log.created_at else None,
#             "session_date": str(session.date).split(" ")[0] if session and session.date else "Unknown"
#         })
#     return res
#
# @router.get("/analytics/class")
# def get_class_analytics(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
#     from app.models.models import ProgramLeaderAssignment, Student, CourseClass, Branch, Section, Subject
#
#     # Must be PL or Admin
#     if current_user.role not in [RoleEnum.ADMIN, RoleEnum.PROGRAM_LEADER]:
#         raise HTTPException(status_code=403, detail="Not authorized")
#
#     scope = None
#     if current_user.role == RoleEnum.PROGRAM_LEADER:
#         scope = db.query(ProgramLeaderAssignment).filter_by(user_id=current_user.id).first()
#         if not scope:
#             raise HTTPException(status_code=403, detail="PL scope not defined")
#
#     # For PL, calculate analytics for their specific cohort
#     if scope:
#         students = db.query(Student).filter_by(
#             class_id=scope.class_id, year=scope.year, branch_id=scope.branch_id, section_id=scope.section_id
#         ).all()
#         sessions = db.query(AttendanceSession).join(
#             FacultyAssignment,
#             (AttendanceSession.faculty_id == FacultyAssignment.faculty_id) &
#             (AttendanceSession.section_id == FacultyAssignment.section_id) &
#             (AttendanceSession.subject_id == FacultyAssignment.subject_id)
#         ).filter(
#             FacultyAssignment.class_id == scope.class_id,
#             FacultyAssignment.year == scope.year,
#             FacultyAssignment.branch_id == scope.branch_id,
#             FacultyAssignment.section_id == scope.section_id
#         ).all()
#     else:
#         # For Admin, just return an error for now since this endpoint is specifically for PL cohort view
#         # Or require section_id param. Let's keep it simple: admin needs section_id query param
#         raise HTTPException(status_code=400, detail="Admin must specify cohort. Not implemented for global.")
#
#     # Calculations
#     student_ids = [s.id for s in students]
#     records = db.query(AttendanceRecord).filter(AttendanceRecord.student_id.in_(student_ids)).all()
#
#     total_students = len(students)
#     total_lectures = sum([calculate_lectures(sess.start_time, sess.end_time) for sess in sessions])
#
#     # Aggregate data
#     total_present_lectures = 0
#     total_possible_lectures = 0
#
#     student_stats = {s.id: {"name": s.name, "roll_number": s.roll_number, "present": 0, "total": 0} for s in students}
#     subject_stats = {}
#
#     session_map = {s.id: s for s in sessions}
#     subject_map = {s.id: s.name for s in db.query(Subject).all()}
#
#     for rec in records:
#         sess = session_map.get(rec.session_id)
#         if not sess: continue
#
#         lec_count = calculate_lectures(sess.start_time, sess.end_time)
#         sub_id = sess.subject_id
#
#         if sub_id not in subject_stats:
#             subject_stats[sub_id] = {"name": subject_map.get(sub_id, "Unknown"), "present": 0, "total": 0}
#
#         student_stats[rec.student_id]["total"] += lec_count
#         subject_stats[sub_id]["total"] += lec_count
#         total_possible_lectures += lec_count
#
#         if rec.status.upper() == "PRESENT":
#             student_stats[rec.student_id]["present"] += lec_count
#             subject_stats[sub_id]["present"] += lec_count
#             total_present_lectures += lec_count
#
#     above_threshold = 0
#     below_threshold = 0
#     for sid, stat in student_stats.items():
#         pct = (stat["present"] / stat["total"] * 100) if stat["total"] > 0 else 0
#         stat["percentage"] = round(pct, 2)
#         if pct >= 75: above_threshold += 1
#         elif stat["total"] > 0: below_threshold += 1
#
#     for sub_id, stat in subject_stats.items():
#         stat["percentage"] = round((stat["present"] / stat["total"] * 100), 2) if stat["total"] > 0 else 0
#
#     overall_percentage = round((total_present_lectures / total_possible_lectures * 100), 2) if total_possible_lectures > 0 else 0
#
#     return {
#         "total_students": total_students,
#         "total_lectures": total_lectures,
#         "overall_percentage": overall_percentage,
#         "present_counts": total_present_lectures,
#         "absent_counts": total_possible_lectures - total_present_lectures,
#         "above_threshold": above_threshold,
#         "below_threshold": below_threshold,
#         "student_stats": list(student_stats.values()),
#         "subject_stats": list(subject_stats.values())
#     }
#
# @router.get("/analytics/student/{student_id}")
# def get_student_analytics(student_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
#     from app.models.models import ProgramLeaderAssignment, Student, Subject
#
#     # Authorize
#     stu = db.query(Student).filter_by(id=student_id).first()
#     if not stu: raise HTTPException(status_code=404, detail="Student not found")
#
#     if current_user.role == RoleEnum.PROGRAM_LEADER:
#         scope = db.query(ProgramLeaderAssignment).filter_by(user_id=current_user.id).first()
#         if not scope or scope.class_id != stu.class_id or scope.year != stu.year or scope.branch_id != stu.branch_id or scope.section_id != stu.section_id:
#             raise HTTPException(status_code=403, detail="Student is out of PL scope")
#     elif current_user.role not in [RoleEnum.ADMIN]:
#         raise HTTPException(status_code=403, detail="Not authorized")
#
#     # Gather data
#     records = db.query(AttendanceRecord).filter_by(student_id=student_id).all()
#     session_ids = [r.session_id for r in records]
#     sessions = db.query(AttendanceSession).filter(AttendanceSession.id.in_(session_ids)).order_by(AttendanceSession.date.desc()).all()
#
#     session_map = {s.id: s for s in sessions}
#     subject_map = {s.id: s.name for s in db.query(Subject).all()}
#
#     total_present = 0
#     total_possible = 0
#     subject_stats = {}
#     history = []
#
#     for r in records:
#         sess = session_map.get(r.session_id)
#         if not sess: continue
#
#         lec_count = calculate_lectures(sess.start_time, sess.end_time)
#         sub_id = sess.subject_id
#
#         if sub_id not in subject_stats:
#             subject_stats[sub_id] = {"name": subject_map.get(sub_id, "Unknown"), "present": 0, "total": 0}
#
#         subject_stats[sub_id]["total"] += lec_count
#         total_possible += lec_count
#
#         if r.status.upper() == "PRESENT":
#             subject_stats[sub_id]["present"] += lec_count
#             total_present += lec_count
#
#         history.append({
#             "date": str(sess.date).split(" ")[0],
#             "subject": subject_map.get(sub_id, "Unknown"),
#             "time": f"{sess.start_time} - {sess.end_time}",
#             "status": r.status.title(),
#             "lectures": lec_count
#         })
#
#     for sub_id, stat in subject_stats.items():
#         stat["percentage"] = round((stat["present"] / stat["total"] * 100), 2) if stat["total"] > 0 else 0
#
#     overall_pct = round((total_present / total_possible * 100), 2) if total_possible > 0 else 0
#
#     return {
#         "student": {"name": stu.name, "roll_number": stu.roll_number, "enrollment_no": stu.enrollment_no},
#         "overall_percentage": overall_pct,
#         "total_lectures": total_possible,
#         "present_lectures": total_present,
#         "absent_lectures": total_possible - total_present,
#         "subject_wise": list(subject_stats.values()),
#         "history": sorted(history, key=lambda x: x['date'], reverse=True),
#         "is_warning": overall_pct < 75 and total_possible > 0
#     }
from datetime import datetime
from typing import List
import uuid
import sqlalchemy

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    User,
    Student,
    AttendanceSession,
    AttendanceRecord,
    FacultyAssignment,
    ProgramLeaderAssignment,
    RoleEnum,
    AttendanceStatus,
    AttendanceAuditLog,
    CourseClass,
    Branch,
    Section,
    Subject,
)

router = APIRouter()


class RecordCreate(BaseModel):
    student_id: str
    status: AttendanceStatus


class SessionCreate(BaseModel):
    section_id: str
    subject_id: str
    date: str
    start_time: str
    end_time: str
    records: List[RecordCreate]


async def one(db, model, *conditions):
    result = await db.execute(select(model).where(*conditions))
    return result.scalars().first()


async def many(db, model, *conditions):
    result = await db.execute(select(model).where(*conditions))
    return result.scalars().all()


def calculate_lectures(start_time_str: str, end_time_str: str) -> int:
    try:
        t1 = datetime.strptime(start_time_str, "%H:%M")
        t2 = datetime.strptime(end_time_str, "%H:%M")
        diff_mins = (t2 - t1).total_seconds() / 60
        return 2 if diff_mins > 60 else 1
    except (ValueError, TypeError):
        return 1


@router.get("/my-assignments")
async def get_my_assignments(
    strict_faculty: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [RoleEnum.FACULTY, RoleEnum.PROGRAM_LEADER]:
        raise HTTPException(403, "Not authorized to access assignments")

    if strict_faculty:
        assignments = await many(
            db, FacultyAssignment,
            FacultyAssignment.faculty_id == current_user.id
        )

    elif current_user.role == RoleEnum.PROGRAM_LEADER:
        scope = await one(
            db, ProgramLeaderAssignment,
            ProgramLeaderAssignment.user_id == current_user.id
        )

        pl_assignments = []
        if scope:
            pl_assignments = await many(
                db, FacultyAssignment,
                FacultyAssignment.class_id == scope.class_id,
                FacultyAssignment.year == scope.year,
                FacultyAssignment.branch_id == scope.branch_id,
                FacultyAssignment.section_id == scope.section_id,
            )

        faculty_assignments = await many(
            db, FacultyAssignment,
            FacultyAssignment.faculty_id == current_user.id
        )

        combined = {
            f"{a.section_id}|{a.subject_id}": a
            for a in pl_assignments + faculty_assignments
        }
        assignments = list(combined.values())

    else:
        assignments = await many(
            db, FacultyAssignment,
            FacultyAssignment.faculty_id == current_user.id
        )

    res = []

    for a in assignments:
        cls = await one(db, CourseClass, CourseClass.id == a.class_id)
        br = await one(db, Branch, Branch.id == a.branch_id)
        sec = await one(db, Section, Section.id == a.section_id)
        sub = await one(db, Subject, Subject.id == a.subject_id)

        if cls and br and sec and sub:
            res.append({
                "class_id": cls.id,
                "class_name": cls.name,
                "year": a.year,
                "branch_id": br.id,
                "branch_name": br.name,
                "section_id": sec.id,
                "section_name": sec.name,
                "subject_id": sub.id,
                "subject_name": sub.name,
                "faculty_id": a.faculty_id,
            })

    return res


@router.post("/sessions")
async def create_session(
    data: SessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.end_time <= data.start_time:
        raise HTTPException(400, "Time To must be strictly after Time From")

    parsed_date = datetime.strptime(
        data.date.split("T")[0], "%Y-%m-%d"
    )

    if current_user.role == RoleEnum.PROGRAM_LEADER:
        scope = await one(
            db, ProgramLeaderAssignment,
            ProgramLeaderAssignment.user_id == current_user.id
        )

        if not scope:
            raise HTTPException(403, "PL scope not found")

        cohort_check = await one(
            db, FacultyAssignment,
            FacultyAssignment.section_id == data.section_id,
            FacultyAssignment.subject_id == data.subject_id,
        )

        if not cohort_check:
            raise HTTPException(400, "Invalid section or subject combination")

        if (
            cohort_check.class_id != scope.class_id
            or cohort_check.year != scope.year
            or cohort_check.branch_id != scope.branch_id
            or cohort_check.section_id != scope.section_id
        ):
            raise HTTPException(
                403,
                "Out of PL scope (Class/Branch/Year/Section mismatch)"
            )

    elif current_user.role == RoleEnum.FACULTY:
        assignment = await one(
            db, FacultyAssignment,
            FacultyAssignment.faculty_id == current_user.id,
            FacultyAssignment.section_id == data.section_id,
            FacultyAssignment.subject_id == data.subject_id,
        )

        if not assignment:
            raise HTTPException(
                403,
                "Unauthorized to mark attendance for this section/subject combination."
            )

    target_assignment = await one(
        db, FacultyAssignment,
        FacultyAssignment.section_id == data.section_id,
        FacultyAssignment.subject_id == data.subject_id,
    )

    if target_assignment:
        result = await db.execute(
            select(AttendanceSession)
            .join(
                FacultyAssignment,
                and_(
                    AttendanceSession.faculty_id == FacultyAssignment.faculty_id,
                    AttendanceSession.section_id == FacultyAssignment.section_id,
                    AttendanceSession.subject_id == FacultyAssignment.subject_id,
                ),
            )
            .where(
                FacultyAssignment.class_id == target_assignment.class_id,
                FacultyAssignment.branch_id == target_assignment.branch_id,
                FacultyAssignment.section_id == target_assignment.section_id,
                AttendanceSession.date == parsed_date,
                AttendanceSession.start_time < data.end_time,
                AttendanceSession.end_time > data.start_time,
            )
        )
        overlapping_session = result.scalars().first()

        if overlapping_session:
            raise HTTPException(
                400,
                f"Overlapping session detected "
                f"({overlapping_session.start_time} - "
                f"{overlapping_session.end_time}) for this Class/Branch/Section."
            )
    else:
        existing_session = await one(
            db, AttendanceSession,
            AttendanceSession.section_id == data.section_id,
            AttendanceSession.date == parsed_date,
            AttendanceSession.start_time == data.start_time,
            AttendanceSession.end_time == data.end_time,
        )

        if existing_session:
            raise HTTPException(
                400,
                "Attendance session already exists for this exact time slot."
            )

    new_session = AttendanceSession(
        id=str(uuid.uuid4()),
        section_id=data.section_id,
        subject_id=data.subject_id,
        faculty_id=current_user.id,
        date=parsed_date,
        start_time=data.start_time,
        end_time=data.end_time,
    )

    db.add(new_session)

    for r in data.records:
        db.add(
            AttendanceRecord(
                id=str(uuid.uuid4()),
                session_id=new_session.id,
                student_id=r.student_id,
                status=r.status,
            )
        )

    try:
        await db.commit()
    except sqlalchemy.exc.IntegrityError:
        await db.rollback()
        raise HTTPException(
            400,
            "Database integrity error. Check duplicates."
        )

    return {
        "message": "Attendance created",
        "session_id": new_session.id,
    }


@router.get("/students/{section_id}")
async def get_students(
    section_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == RoleEnum.PROGRAM_LEADER:
        scope = await one(
            db, ProgramLeaderAssignment,
            ProgramLeaderAssignment.user_id == current_user.id
        )
        if not scope or scope.section_id != section_id:
            raise HTTPException(403, "Out of PL scope")

    elif current_user.role == RoleEnum.FACULTY:
        assignment = await one(
            db, FacultyAssignment,
            FacultyAssignment.faculty_id == current_user.id,
            FacultyAssignment.section_id == section_id,
        )
        if not assignment:
            raise HTTPException(403, "Unauthorized section access")

    return await many(
        db, Student,
        Student.section_id == section_id
    )


@router.get("/report/options")
async def get_report_options(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == RoleEnum.PROGRAM_LEADER:
        scope = await one(
            db, ProgramLeaderAssignment,
            ProgramLeaderAssignment.user_id == current_user.id
        )
        if not scope:
            assignments = []
        else:
            assignments = await many(
                db, FacultyAssignment,
                FacultyAssignment.class_id == scope.class_id,
                FacultyAssignment.year == scope.year,
                FacultyAssignment.branch_id == scope.branch_id,
                FacultyAssignment.section_id == scope.section_id,
            )

    elif current_user.role == RoleEnum.FACULTY:
        assignments = await many(
            db, FacultyAssignment,
            FacultyAssignment.faculty_id == current_user.id
        )
    else:
        result = await db.execute(select(FacultyAssignment))
        assignments = result.scalars().all()

    res = []

    for a in assignments:
        cls = await one(db, CourseClass, CourseClass.id == a.class_id)
        br = await one(db, Branch, Branch.id == a.branch_id)
        sec = await one(db, Section, Section.id == a.section_id)
        sub = await one(db, Subject, Subject.id == a.subject_id)

        if cls and br and sec and sub:
            res.append({
                "class_id": cls.id,
                "class_name": cls.name,
                "year": a.year,
                "branch_id": br.id,
                "branch_name": br.name,
                "section_id": sec.id,
                "section_name": sec.name,
                "subject_id": sub.id,
                "subject_name": sub.name,
            })

    return res


@router.get("/report/subject")
async def get_subject_report(
    section_id: str,
    subject_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == RoleEnum.PROGRAM_LEADER:
        scope = await one(
            db, ProgramLeaderAssignment,
            ProgramLeaderAssignment.user_id == current_user.id
        )

        if not scope or scope.section_id != section_id:
            raise HTTPException(403, "Out of PL scope")

        cohort_check = await one(
            db, FacultyAssignment,
            FacultyAssignment.section_id == section_id,
            FacultyAssignment.subject_id == subject_id,
        )

        if not cohort_check or cohort_check.class_id != scope.class_id:
            raise HTTPException(403, "Out of PL scope")

    elif current_user.role == RoleEnum.FACULTY:
        assignment = await one(
            db, FacultyAssignment,
            FacultyAssignment.faculty_id == current_user.id,
            FacultyAssignment.section_id == section_id,
            FacultyAssignment.subject_id == subject_id,
        )

        if not assignment:
            raise HTTPException(
                403,
                "Unauthorized to view reports for this section/subject."
            )

    students = await many(
        db, Student,
        Student.section_id == section_id
    )

    sessions = await many(
        db, AttendanceSession,
        AttendanceSession.section_id == section_id,
        AttendanceSession.subject_id == subject_id,
    )

    session_ids = [s.id for s in sessions]
    total_sessions = len(session_ids)

    stats = {
        s.id: {"present": 0, "absent": 0}
        for s in students
    }

    if session_ids:
        result = await db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.session_id.in_(session_ids)
            )
        )
        records = result.scalars().all()

        for r in records:
            if r.student_id in stats:
                if r.status == AttendanceStatus.PRESENT:
                    stats[r.student_id]["present"] += 1
                else:
                    stats[r.student_id]["absent"] += 1

    report = []

    for s in students:
        attended = stats[s.id]["present"]
        percentage = (
            attended / total_sessions * 100
            if total_sessions > 0 else 0
        )

        report.append({
            "student_id": s.id,
            "name": s.name,
            "roll_number": s.roll_number,
            "total_sessions": total_sessions,
            "attended": attended,
            "percentage": round(percentage, 2),
        })

    return sorted(report, key=lambda x: x["name"])


@router.get("/my-attendance")
async def get_my_attendance(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != RoleEnum.STUDENT:
        raise HTTPException(
            403,
            "Only students can access this endpoint"
        )

    student = await one(
        db, Student,
        Student.user_id == current_user.id
    )

    if not student:
        raise HTTPException(
            404,
            "Student profile not found"
        )

    records = await many(
        db, AttendanceRecord,
        AttendanceRecord.student_id == student.id
    )

    session_ids = [r.session_id for r in records]

    sessions = []
    if session_ids:
        result = await db.execute(
            select(AttendanceSession).where(
                AttendanceSession.id.in_(session_ids)
            )
        )
        sessions = result.scalars().all()

    sessions_map = {s.id: s for s in sessions}

    result = await db.execute(select(Subject))
    subjects = {
        s.id: s.name
        for s in result.scalars().all()
    }

    result = await db.execute(
        select(User).where(User.role == RoleEnum.FACULTY)
    )
    faculties = {
        f.id: f.name
        for f in result.scalars().all()
    }

    subject_stats = {}
    history = []

    overall_total = 0
    overall_present = 0

    for r in records:
        sess = sessions_map.get(r.session_id)
        if not sess:
            continue

        subj_name = subjects.get(
            sess.subject_id,
            "Unknown Subject"
        )
        fac_name = faculties.get(
            sess.faculty_id,
            "Unknown Faculty"
        )

        lec_count = calculate_lectures(
            sess.start_time,
            sess.end_time
        )

        if sess.subject_id not in subject_stats:
            subject_stats[sess.subject_id] = {
                "subject_id": sess.subject_id,
                "subject_name": subj_name,
                "total": 0,
                "present": 0,
                "absent": 0,
            }

        subject_stats[sess.subject_id]["total"] += lec_count
        overall_total += lec_count

        if r.status.upper() == "PRESENT":
            subject_stats[sess.subject_id]["present"] += lec_count
            overall_present += lec_count
        else:
            subject_stats[sess.subject_id]["absent"] += lec_count

        history.append({
            "id": r.id,
            "date": str(sess.date).split(" ")[0],
            "subject": subj_name,
            "faculty": fac_name,
            "time": f"{sess.start_time} - {sess.end_time}",
            "lectures": lec_count,
            "status": r.status.title(),
        })

    for stats in subject_stats.values():
        stats["percentage"] = (
            round(
                stats["present"] / stats["total"] * 100,
                2
            )
            if stats["total"] > 0 else 0
        )
        stats["status"] = (
            "Good"
            if stats["percentage"] >= 75
            else "Defaulter"
        )

    overall_percentage = (
        round(overall_present / overall_total * 100, 2)
        if overall_total > 0 else 0
    )

    daily = {}

    for h in history:
        d = h["date"]

        if d not in daily:
            daily[d] = {
                "present": 0,
                "absent": 0,
                "total": 0,
            }

        daily[d]["total"] += h["lectures"]

        if h["status"].upper() == "PRESENT":
            daily[d]["present"] += h["lectures"]
        else:
            daily[d]["absent"] += h["lectures"]

    trend = [
        {
            "date": k,
            "percentage": round(
                v["present"] / v["total"] * 100
            )
            if v["total"] > 0 else 0,
        }
        for k, v in sorted(daily.items())[-14:]
    ]

    return {
        "overall": {
            "percentage": overall_percentage,
            "total_lectures": overall_total,
            "present_lectures": overall_present,
            "absent_lectures": overall_total - overall_present,
            "is_defaulter": (
                overall_percentage < 75
                and overall_total > 0
            ),
        },
        "subject_wise": list(subject_stats.values()),
        "history": sorted(
            history,
            key=lambda x: x["date"],
            reverse=True,
        ),
        "trend": trend,
    }


@router.put("/sessions/{session_id}")
async def update_session(
    session_id: str,
    data: SessionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.end_time <= data.start_time:
        raise HTTPException(
            400,
            "Time To must be strictly after Time From"
        )

    session = await one(
        db, AttendanceSession,
        AttendanceSession.id == session_id
    )

    if not session:
        raise HTTPException(
            404,
            "Session not found"
        )

    if current_user.role == RoleEnum.PROGRAM_LEADER:
        scope = await one(
            db, ProgramLeaderAssignment,
            ProgramLeaderAssignment.user_id == current_user.id
        )

        if not scope:
            raise HTTPException(
                403,
                "PL scope not found"
            )

        cohort_check = await one(
            db, FacultyAssignment,
            FacultyAssignment.section_id == data.section_id,
            FacultyAssignment.subject_id == data.subject_id,
        )

        if not cohort_check:
            raise HTTPException(
                400,
                "Invalid section/subject"
            )

        if (
            cohort_check.class_id != scope.class_id
            or cohort_check.year != scope.year
            or cohort_check.branch_id != scope.branch_id
            or cohort_check.section_id != scope.section_id
        ):
            raise HTTPException(
                403,
                "Out of PL scope (Class/Branch/Year/Section mismatch)"
            )

    elif current_user.role == RoleEnum.FACULTY:
        assignment = await one(
            db, FacultyAssignment,
            FacultyAssignment.faculty_id == current_user.id,
            FacultyAssignment.section_id == data.section_id,
            FacultyAssignment.subject_id == data.subject_id,
        )

        if not assignment:
            raise HTTPException(
                403,
                "Unauthorized to mark attendance for this section/subject combination."
            )

    elif current_user.role != RoleEnum.ADMIN:
        raise HTTPException(
            403,
            "Not authorized"
        )

    parsed_date = datetime.strptime(
        data.date.split("T")[0],
        "%Y-%m-%d"
    )

    target_assignment = await one(
        db, FacultyAssignment,
        FacultyAssignment.section_id == data.section_id,
        FacultyAssignment.subject_id == data.subject_id,
    )

    if target_assignment:
        result = await db.execute(
            select(AttendanceSession)
            .join(
                FacultyAssignment,
                and_(
                    AttendanceSession.faculty_id == FacultyAssignment.faculty_id,
                    AttendanceSession.section_id == FacultyAssignment.section_id,
                    AttendanceSession.subject_id == FacultyAssignment.subject_id,
                ),
            )
            .where(
                FacultyAssignment.class_id == target_assignment.class_id,
                FacultyAssignment.branch_id == target_assignment.branch_id,
                FacultyAssignment.section_id == target_assignment.section_id,
                AttendanceSession.date == parsed_date,
                AttendanceSession.start_time < data.end_time,
                AttendanceSession.end_time > data.start_time,
                AttendanceSession.id != session_id,
            )
        )

        overlapping_session = result.scalars().first()

        if overlapping_session:
            raise HTTPException(
                400,
                f"Overlapping session detected "
                f"({overlapping_session.start_time} - "
                f"{overlapping_session.end_time}) for this Class/Branch/Section."
            )

    session.date = parsed_date
    session.start_time = data.start_time
    session.end_time = data.end_time

    for rec_data in data.records:
        rec = await one(
            db,
            AttendanceRecord,
            AttendanceRecord.session_id == session_id,
            AttendanceRecord.student_id == rec_data.student_id,
        )

        if rec:
            if rec.status != rec_data.status:
                if current_user.role == RoleEnum.PROGRAM_LEADER:
                    # Preserves the audit-log fields used by the
                    # existing router/model in the supplied project.
                    audit = AttendanceAuditLog(
                        id=str(uuid.uuid4()),
                        session_id=session_id,
                        student_id=rec_data.student_id,
                        changed_by=current_user.id,
                        previous_status=rec.status,
                        new_status=rec_data.status,
                    )
                    db.add(audit)

                rec.status = rec_data.status

        else:
            db.add(
                AttendanceRecord(
                    id=str(uuid.uuid4()),
                    session_id=session_id,
                    student_id=rec_data.student_id,
                    status=rec_data.status,
                )
            )

    await db.commit()

    return {
        "message": "Attendance updated successfully"
    }


@router.get("/sessions/date")
async def get_sessions_by_date(
    section_id: str,
    subject_id: str,
    date: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AttendanceSession).where(
            AttendanceSession.section_id == section_id,
            AttendanceSession.subject_id == subject_id,
            AttendanceSession.date.like(f"{date}%"),
        )
    )

    sessions = result.scalars().all()

    res = []

    for s in sessions:
        records = await many(
            db,
            AttendanceRecord,
            AttendanceRecord.session_id == s.id
        )

        res.append({
            "id": s.id,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "records": [
                {
                    "student_id": r.student_id,
                    "status": r.status,
                }
                for r in records
            ],
        })

    return res


@router.get("/audit-logs")
async def get_audit_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [
        RoleEnum.ADMIN,
        RoleEnum.PROGRAM_LEADER,
    ]:
        raise HTTPException(
            403,
            "Not authorized to view audit logs"
        )

    result = await db.execute(
        select(AttendanceAuditLog)
        .order_by(AttendanceAuditLog.created_at.desc())
        .limit(100)
    )
    logs = result.scalars().all()

    res = []

    for log in logs:
        student = await one(
            db, Student,
            Student.id == log.student_id
        )
        changer = await one(
            db, User,
            User.id == log.changed_by
        )
        session = await one(
            db, AttendanceSession,
            AttendanceSession.id == log.session_id
        )

        res.append({
            "id": log.id,
            "student_name": student.name if student else "Unknown",
            "roll_number": student.roll_number if student else "-",
            "changed_by": changer.name if changer else "Unknown",
            "changer_role": changer.role if changer else "Unknown",
            "previous_status": log.previous_status,
            "new_status": log.new_status,
            "timestamp": (
                log.created_at.isoformat()
                if log.created_at else None
            ),
            "session_date": (
                str(session.date).split(" ")[0]
                if session and session.date
                else "Unknown"
            ),
        })

    return res


@router.get("/analytics/class")
async def get_class_analytics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [
        RoleEnum.ADMIN,
        RoleEnum.PROGRAM_LEADER,
    ]:
        raise HTTPException(
            403,
            "Not authorized"
        )

    scope = None

    if current_user.role == RoleEnum.PROGRAM_LEADER:
        scope = await one(
            db,
            ProgramLeaderAssignment,
            ProgramLeaderAssignment.user_id == current_user.id,
        )

        if not scope:
            raise HTTPException(
                403,
                "PL scope not defined"
            )

    if not scope:
        raise HTTPException(
            400,
            "Admin must specify cohort. Not implemented for global."
        )

    students = await many(
        db,
        Student,
        Student.class_id == scope.class_id,
        Student.year == scope.year,
        Student.branch_id == scope.branch_id,
        Student.section_id == scope.section_id,
    )

    result = await db.execute(
        select(AttendanceSession)
        .join(
            FacultyAssignment,
            and_(
                AttendanceSession.faculty_id == FacultyAssignment.faculty_id,
                AttendanceSession.section_id == FacultyAssignment.section_id,
                AttendanceSession.subject_id == FacultyAssignment.subject_id,
            ),
        )
        .where(
            FacultyAssignment.class_id == scope.class_id,
            FacultyAssignment.year == scope.year,
            FacultyAssignment.branch_id == scope.branch_id,
            FacultyAssignment.section_id == scope.section_id,
        )
    )

    sessions = result.scalars().all()

    student_ids = [s.id for s in students]

    records = []

    if student_ids:
        result = await db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.student_id.in_(student_ids)
            )
        )
        records = result.scalars().all()

    total_students = len(students)

    total_lectures = sum(
        calculate_lectures(
            sess.start_time,
            sess.end_time
        )
        for sess in sessions
    )

    total_present_lectures = 0
    total_possible_lectures = 0

    student_stats = {
        s.id: {
            "name": s.name,
            "roll_number": s.roll_number,
            "present": 0,
            "total": 0,
        }
        for s in students
    }

    subject_stats = {}
    session_map = {s.id: s for s in sessions}

    result = await db.execute(select(Subject))
    subject_map = {
        s.id: s.name
        for s in result.scalars().all()
    }

    for rec in records:
        sess = session_map.get(rec.session_id)

        if not sess or rec.student_id not in student_stats:
            continue

        lec_count = calculate_lectures(
            sess.start_time,
            sess.end_time
        )

        sub_id = sess.subject_id

        if sub_id not in subject_stats:
            subject_stats[sub_id] = {
                "name": subject_map.get(
                    sub_id,
                    "Unknown"
                ),
                "present": 0,
                "total": 0,
            }

        student_stats[rec.student_id]["total"] += lec_count
        subject_stats[sub_id]["total"] += lec_count
        total_possible_lectures += lec_count

        if rec.status.upper() == "PRESENT":
            student_stats[rec.student_id]["present"] += lec_count
            subject_stats[sub_id]["present"] += lec_count
            total_present_lectures += lec_count

    above_threshold = 0
    below_threshold = 0

    for stat in student_stats.values():
        pct = (
            stat["present"] / stat["total"] * 100
            if stat["total"] > 0 else 0
        )

        stat["percentage"] = round(pct, 2)

        if pct >= 75:
            above_threshold += 1
        elif stat["total"] > 0:
            below_threshold += 1

    for stat in subject_stats.values():
        stat["percentage"] = (
            round(
                stat["present"] / stat["total"] * 100,
                2
            )
            if stat["total"] > 0 else 0
        )

    overall_percentage = (
        round(
            total_present_lectures /
            total_possible_lectures * 100,
            2
        )
        if total_possible_lectures > 0
        else 0
    )

    return {
        "total_students": total_students,
        "total_lectures": total_lectures,
        "overall_percentage": overall_percentage,
        "present_counts": total_present_lectures,
        "absent_counts": (
            total_possible_lectures -
            total_present_lectures
        ),
        "above_threshold": above_threshold,
        "below_threshold": below_threshold,
        "student_stats": list(student_stats.values()),
        "subject_stats": list(subject_stats.values()),
    }


@router.get("/analytics/student/{student_id}")
async def get_student_analytics(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stu = await one(
        db,
        Student,
        Student.id == student_id
    )

    if not stu:
        raise HTTPException(
            404,
            "Student not found"
        )

    if current_user.role == RoleEnum.PROGRAM_LEADER:
        scope = await one(
            db,
            ProgramLeaderAssignment,
            ProgramLeaderAssignment.user_id == current_user.id,
        )

        if (
            not scope
            or scope.class_id != stu.class_id
            or scope.year != stu.year
            or scope.branch_id != stu.branch_id
            or scope.section_id != stu.section_id
        ):
            raise HTTPException(
                403,
                "Student is out of PL scope"
            )

    elif current_user.role != RoleEnum.ADMIN:
        raise HTTPException(
            403,
            "Not authorized"
        )

    records = await many(
        db,
        AttendanceRecord,
        AttendanceRecord.student_id == student_id
    )

    session_ids = [r.session_id for r in records]

    sessions = []

    if session_ids:
        result = await db.execute(
            select(AttendanceSession)
            .where(AttendanceSession.id.in_(session_ids))
            .order_by(AttendanceSession.date.desc())
        )
        sessions = result.scalars().all()

    session_map = {s.id: s for s in sessions}

    result = await db.execute(select(Subject))
    subject_map = {
        s.id: s.name
        for s in result.scalars().all()
    }

    total_present = 0
    total_possible = 0
    subject_stats = {}
    history = []

    for r in records:
        sess = session_map.get(r.session_id)

        if not sess:
            continue

        lec_count = calculate_lectures(
            sess.start_time,
            sess.end_time
        )

        sub_id = sess.subject_id

        if sub_id not in subject_stats:
            subject_stats[sub_id] = {
                "name": subject_map.get(
                    sub_id,
                    "Unknown"
                ),
                "present": 0,
                "total": 0,
            }

        subject_stats[sub_id]["total"] += lec_count
        total_possible += lec_count

        if r.status.upper() == "PRESENT":
            subject_stats[sub_id]["present"] += lec_count
            total_present += lec_count

        history.append({
            "date": str(sess.date).split(" ")[0],
            "subject": subject_map.get(
                sub_id,
                "Unknown"
            ),
            "time": (
                f"{sess.start_time} - "
                f"{sess.end_time}"
            ),
            "status": r.status.title(),
            "lectures": lec_count,
        })

    for stat in subject_stats.values():
        stat["percentage"] = (
            round(
                stat["present"] /
                stat["total"] * 100,
                2
            )
            if stat["total"] > 0
            else 0
        )

    overall_pct = (
        round(
            total_present /
            total_possible * 100,
            2
        )
        if total_possible > 0
        else 0
    )

    return {
        "student": {
            "name": stu.name,
            "roll_number": stu.roll_number,
            "enrollment_no": stu.enrollment_no,
        },
        "overall_percentage": overall_pct,
        "total_lectures": total_possible,
        "present_lectures": total_present,
        "absent_lectures": (
            total_possible -
            total_present
        ),
        "subject_wise": list(subject_stats.values()),
        "history": sorted(
            history,
            key=lambda x: x["date"],
            reverse=True,
        ),
        "is_warning": (
            overall_pct < 75
            and total_possible > 0
        ),
    }
