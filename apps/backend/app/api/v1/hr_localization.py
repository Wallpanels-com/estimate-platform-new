"""English display translations restricted to saved, HR-authorized content."""
import uuid
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.hr import Candidate, Vacancy, CandidateAIReview
from app.services import hr_ai, hr_translation

router = APIRouter()


class LocalizeInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    scope: Literal['vacancies', 'candidate', 'candidates']
    candidate_id: uuid.UUID | None = None
    candidate_ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)
    texts: list[str] = Field(min_length=1, max_length=30)


def strings(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for item in value.values() for s in strings(item)]
    if isinstance(value, list):
        return [s for item in value for s in strings(item)]
    return []


@router.post('/localize')
async def english_display(body: LocalizeInput, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    if sum(len(t) for t in body.texts) > 14000 or any(len(t) > 8000 for t in body.texts):
        raise HTTPException(422, 'Choose a smaller batch of HR text.')
    if body.scope == 'vacancies':
        allowed = {s for v in (await db.execute(select(Vacancy))).scalars() for s in (v.name, v.description)}
    elif body.scope == 'candidates':
        rows = (await db.execute(select(Candidate).where(Candidate.id.in_(body.candidate_ids)))).scalars()
        allowed = {s for c in rows for s in [*c.answers, *strings(c.answers)]}
    else:
        c = await db.get(Candidate, body.candidate_id) if body.candidate_id else None
        if not c:
            raise HTTPException(404, 'Candidate not found.')
        # Source answers are display data; names, contacts, private HR notes and files
        # are not collected for translation. Application/review text stays unchanged.
        allowed = set(c.answers) | set(strings(c.answers))
        review = await db.get(CandidateAIReview, c.id)
        if review:
            from app.api.v1.hr_ai import output
            v = await db.get(Vacancy, c.vacancy_id)
            shown = output(review, hr_ai.source_data(c, v))
            allowed.update(strings(shown['content']))
            allowed.add(shown['message_draft'])
    if any(t not in allowed for t in body.texts):
        raise HTTPException(409, 'HR content changed. Reopen the card and try again.')
    try:
        return {'translations': await hr_translation.localize(db, body.texts)}
    except hr_ai.AIUnavailable as error:
        raise HTTPException(error.status, error.message) from None
