"""Read GHL transcripts; transcribe existing recordings in Groq without CRM writes."""
from datetime import timedelta
from math import isfinite
import httpx
from sqlalchemy import select
from app.core.config import settings
from app.models.sales import SalesRecord, SalesSync
from .store import get_record, save, enqueue, loc, now, stamp
from .client import GhlError


def speech_segments(data):
    """Keep ASR timestamps and text, never invent speaker labels."""
    result=[]
    for segment in data.get('segments',[]):
        if not isinstance(segment,dict):continue
        if segment.get('no_speech_prob',0)>.8 and segment.get('avg_logprob',0)<-1:continue
        text=str(segment.get('text') or '').strip()
        if text:
            item={'text':text}
            start=segment.get('start')
            if isinstance(start,(int,float)) and isfinite(start) and start>=0:item['startTime']=round(start*1000)
            result.append(item)
    return result


async def read_ghl_transcript(db,c,job):
    p=job.payload;ident=p['id'];old=await get_record(db,'transcripts',ident)
    if old and (old.payload.get('segments') or old.payload.get('availability') in ('no_speech','not_recorded','too_large')):return True
    message=await get_record(db,'messages',ident)
    payload={'id':ident,'contactId':p.get('contactId'),'dateAdded':message.payload.get('dateAdded') if message else None,'segments':[]}
    voice=await db.scalar(select(SalesRecord).where(SalesRecord.location_id==loc(),SalesRecord.kind=='calls',SalesRecord.payload['messageId'].astext==ident).limit(1))
    if voice and voice.payload.get('transcript'):
        segments=[{'text':voice.payload['transcript']}];source='ghl_voice_ai'
    else:
        try:data=await c.get(f'/conversations/locations/{loc()}/messages/{ident}/transcription')
        except GhlError as error:
            if error.status not in (400,404):raise
            data=[]
        segments=data if isinstance(data,list) else data.get('transcriptions',data.get('transcription',data.get('data',[])))
        if isinstance(segments,str):segments=[{'text':segments}]
        if not isinstance(segments,list):raise ValueError('Unsupported transcript shape')
        segments=[s for s in segments if isinstance(s,dict) and (s.get('text') or s.get('transcript'))]
        source='ghl'
    if segments:
        await save(db,'transcripts',{**payload,'segments':segments,'availability':'available','transcript_source':source})
        # Voice AI logs and conversation messages can reference the same call.
        # Reuse one analysis identity instead of paying to review it twice.
        if source=='ghl_voice_ai':
            await enqueue(db,'analysis','call:'+voice.external_id,{'source_kind':'calls','id':voice.external_id,'contactId':p.get('contactId')},priority=max(20,job.priority))
        else:
            await enqueue(db,'analysis','transcript:'+ident,{'source_kind':'transcripts','id':ident,'contactId':p.get('contactId')},priority=max(20,job.priority))
    elif job.priority>=5:
        await save(db,'transcripts',{**payload,'availability':'queued'})
        await enqueue(db,'asr',ident,p,priority=job.priority)
    else:
        await save(db,'transcripts',{**payload,'availability':'not_available'})
    return True


async def transcribe_recording(db,c,job):
    p=job.payload;ident=p['id'];old=await get_record(db,'transcripts',ident)
    if old and (old.payload.get('segments') or old.payload.get('availability') in ('no_speech','not_recorded','too_large')):return True
    message=await get_record(db,'messages',ident)
    payload={'id':ident,'contactId':p.get('contactId'),'dateAdded':message.payload.get('dateAdded') if message else None,'segments':[],'transcript_source':'groq'}
    async def state(value,retry_at=None):
        await save(db,'transcripts',{**payload,'availability':value,**({'retry_at':retry_at.isoformat()} if retry_at else {})})
    if not settings.SALES_GROQ_API_KEY:
        job.next_run=now()+timedelta(hours=1);await state('unavailable',job.next_run);return False
    usage=await db.get(SalesSync,(loc(),'transcription_usage'))
    if usage is None:
        usage=SalesSync(location_id=loc(),resource='transcription_usage',state={},next_run=now());db.add(usage)
    midnight=now().replace(hour=0,minute=0,second=0,microsecond=0);day=midnight.date().isoformat()
    count=usage.state.get('requests',0) if usage.state.get('day')==day else 0
    blocked=stamp(usage.state.get('blocked_until'))
    if blocked and blocked>now():
        job.next_run=blocked;await state('rate_limited',blocked);return False
    if settings.SALES_ASR_DAILY_LIMIT>0 and count>=settings.SALES_ASR_DAILY_LIMIT:
        job.next_run=midnight+timedelta(days=1);await state('daily_limit',job.next_run);return False
    try:audio,mime=await c.get(f'/conversations/messages/{ident}/locations/{loc()}/recording',binary=True)
    except GhlError as error:
        if error.status in (400,404):
            call_time=stamp(payload.get('dateAdded'))
            if call_time and now()-call_time<timedelta(minutes=15):
                job.next_run=now()+timedelta(minutes=2);await state('queued',job.next_run);return False
            await state('not_recorded');return True
        raise
    if not audio or not mime.startswith(('audio/','application/octet-stream')):
        await state('not_recorded');return True
    if len(audio)>25*1024*1024:await state('too_large');return True
    usage.state={'day':day,'requests':count+1,'limit':settings.SALES_ASR_DAILY_LIMIT};usage.last_success=now();usage.error=None
    await state('processing');await db.commit()
    extension='mp3' if 'mpeg' in mime else 'ogg' if 'ogg' in mime else 'wav'
    async with httpx.AsyncClient(timeout=httpx.Timeout(120,connect=10),follow_redirects=False) as client:
        response=await client.post('https://api.groq.com/openai/v1/audio/transcriptions',headers={'Authorization':'Bearer '+settings.SALES_GROQ_API_KEY},
            files={'file':('call.'+extension,audio,mime.split(';')[0])},data={'model':'whisper-large-v3-turbo','response_format':'verbose_json','timestamp_granularities[]':'segment','temperature':'0'})
    if not response.is_success:
        job.attempts+=1;job.error=f'Groq transcription HTTP {response.status_code}; retry scheduled.'
        job.next_run=now()+timedelta(minutes=min(60,2**min(job.attempts,6)))
        if response.status_code==429:
            try:delay=float(response.headers.get('retry-after','60'))
            except ValueError:delay=60
            job.next_run=now()+timedelta(seconds=max(30,min(86400,delay)))
            usage.state={**usage.state,'requests':count,'blocked_until':job.next_run.isoformat()}
            await state('rate_limited',job.next_run)
        else:await state('unavailable',job.next_run)
        return False
    segments=speech_segments(response.json())
    await save(db,'transcripts',{**payload,'segments':segments,'availability':'available' if segments else 'no_speech'})
    if segments:await enqueue(db,'analysis','transcript:'+ident,{'source_kind':'transcripts','id':ident,'contactId':p.get('contactId')},priority=max(job.priority,20))
    return True
