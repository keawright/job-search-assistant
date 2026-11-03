"""Private copy-on-write search reports, never edits the application tracker."""
from pathlib import Path
import json
import csv
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font, PatternFill, Alignment

HEADERS=['Company','Job title','Location','Remote/hybrid/on-site','Salary range','Job posting date',
         'Date discovered','Fit classification','Fit score','Why I am a good fit','Potential concerns',
         'Application URL','Application status','Decision reason','Work-life balance','Evidence source',
         'Posting application status','Application status checked on','Verification URL','Verification method','Verification evidence']


def safe(value):
    if isinstance(value,(int,float)) and not isinstance(value,bool): return value
    value=ILLEGAL_CHARACTERS_RE.sub('',str(value or ''))[:32767]
    return "'"+value if value.startswith(('=','+','-','@')) else value


def row(posting,state,reason,review):
    a=review.get('assessment',{})
    classification=reason if state=='recommended' else ('Stretch' if any(a.get(k,{}).get('rating')=='stretch' for k in ['leadership_fit','technical_fit','career_alignment','opportunity_quality']) else 'Not recommended')
    if state=='verification' and not a: classification='Needs assessment'
    return [posting.company,posting.title,posting.location,posting.arrangement,posting.salary or review.get('compensation',''),
            posting.posted,posting.discovered,classification,4 if classification=='Strong Fit' else 3 if classification=='Good Fit' else '',
            a.get('summary',''), '\n'.join(a.get('uncertainties',[])+[g.get('description','') for g in a.get('gaps',[])]),
            posting.url,'Not applied',reason,review.get('work_life_balance','Unknown'),posting.source,
            posting.application_status,posting.application_checked_on,posting.application_verification_url,
            posting.application_verification_method,posting.application_verification_evidence]


def coverage_summary(results, coverage):
    from collections import Counter
    queries=[c for c in coverage if c.get('kind')=='web query']
    sources=[c for c in coverage if c.get('method') in {'Public employer ATS feed','Direct employer career-page links'}]
    failed=sum(c.get('status')!='success' for c in queries)+sum(bool(c.get('error')) for c in sources)
    deferred=sum(c.get('deferred',0) for c in coverage)
    status='Search incomplete' if failed or deferred or not (queries or sources) else 'Planned sources completed; coverage is not exhaustive'
    return dict(status=status,queries_planned=sum(c.get('planned',0) for c in coverage) or len(queries),queries_attempted=sum(bool(c.get('attempts')) for c in queries),
                queries_completed=sum(c.get('status')=='success' for c in queries),queries_pending=deferred,
                sources_checked=len(sources),sources_reached=sum(not c.get('error') for c in sources),
                unique_candidates=len(results),assessed=sum(bool(r[3]) for r in results),
                decisions=dict(Counter(r[1] for r in results)),reasons=dict(Counter(r[2] for r in results)),
                leads_by_source=dict(Counter(r[0].source for r in results if r[1] in {'recommended','verification'})))


def export(folder,run,results,coverage,*,title="New job opportunities"):
    from .eligibility import exclusion_reason
    results=[(p,'rejected',exclusion_reason(p),review)
             if state in {'recommended','verification'} and exclusion_reason(p) else (p,state,reason,review)
             for p,state,reason,review in results]
    from .verification import current_application_verified, current_closure_verified
    results=[(p,'rejected','Employer vacancy closed or removed: '+p.application_verification_evidence,review)
             if state in {'recommended','verification'} and current_closure_verified(p) else (p,state,reason,review)
             for p,state,reason,review in results]
    results=[(p,'verification','Recommendation withheld: current application acceptance is not verified today',review)
             if state=='recommended' and not current_application_verified(p) else (p,state,reason,review)
             for p,state,reason,review in results]
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    xlsx=folder/f'job-search-{run}.xlsx'; md=folder/f'job-search-{run}.md'
    if xlsx.exists() or md.exists(): raise FileExistsError('Search report already exists')
    summary=coverage_summary(results,coverage)
    wb=Workbook(); wb.remove(wb.active)
    summary_ws=wb.create_sheet('Run Summary')
    summary_ws.append(['Measure','Result'])
    for key,value in summary.items():
        if isinstance(value,dict):
            for label,count in value.items(): summary_ws.append([safe(key+': '+label),safe(count)])
        else: summary_ws.append([safe(key),safe(value)])

    groups={'Recommended Jobs':{'recommended'},'Needs Verification':{'verification'},
            'Rejected Jobs':{'rejected','duplicate','superseded'}}
    for name,states in groups.items():
        ws=wb.create_sheet(name); ws.append(HEADERS)
        for p,state,reason,review in results:
            if state in states:
                ws.append([safe(x) for x in row(p,state,reason,review)])
                if p.url.startswith(('https://','http://')):
                    ws.cell(ws.max_row,12).hyperlink=p.url
                    ws.cell(ws.max_row,12).style='Hyperlink'
    ws=wb.create_sheet('Search Coverage')
    ws.append(['Source','Search method','Date checked','Number of postings discovered','Number assessed','Errors or access limitations','Provider attempts'])
    for c in coverage: ws.append([safe(c.get(k,'')) for k in ['source','method','checked','discovered','assessed','error']]+[safe(json.dumps(c.get('attempts',[])))])
    for ws in wb:
        ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
        for cell in ws[1]: cell.font=Font(bold=True,color='FFFFFF'); cell.fill=PatternFill('solid',fgColor='24445C')
        for col in ws.columns: ws.column_dimensions[col[0].column_letter].width=32
        for cells in ws.iter_rows(min_row=2):
            for cell in cells: cell.alignment=Alignment(vertical='top',wrap_text=True)
        if ws.title!='Search Coverage':
            for column in ['J','K','N','O']: ws.column_dimensions[column].width=65
            ws.column_dimensions['B'].width=48
            ws.column_dimensions['L'].width=55
    with xlsx.open('xb') as stream: wb.save(stream)
    wb.close()
    for name in groups:
        with (folder/f'{xlsx.stem}-{name.lower().replace(" ","-")}.csv').open('x',encoding='utf-8-sig',newline='') as stream:
            writer=csv.writer(stream); writer.writerow(HEADERS)
            for p,state,reason,review in results:
                if state in groups[name]: writer.writerow([safe(x) for x in row(p,state,reason,review)])
    recommendations=[r for r in results if r[1]=='recommended']
    lines=['# '+title,f'Run: {run}',
           '**'+summary['status']+'**',
           'Zero recommendations does not establish that no suitable jobs exist.',
           f'{len(recommendations)} recommendations; {sum(r[1]=="verification" for r in results)} need verification.',
           'Fit score is an ordinal label (Strong=4, Good=3), not a hiring probability.',
           'Posting dates remain blank when unknown; crawl/update dates are not original posting dates.','']
    for i,(p,state,reason,review) in enumerate(recommendations[:20],1):
        lines += [f'## {i}. {p.company} — {p.title}',f'[{reason}]({p.url})',review['assessment']['summary'],
                  'Concerns: '+ '; '.join(review['assessment']['uncertainties']), '']
    if not recommendations: lines += ['No new positions passed every recommendation gate. Verification candidates are not recommendations.','']
    verification=[r for r in results if r[1]=='verification']
    if verification:
        lines += ['## Worth verifying, not recommendations',
                  'These roles have useful fit evidence but fail one or more required recommendation gates.']
        for p,state,reason,review in verification[:10]:
            lines += [f'- [{p.company} - {p.title}]({p.url}): {reason}. '+review.get('assessment',{}).get('summary','Fit review pending')]
        lines.append('')
    lines += ['## Search funnel',
              f"- Web queries: {summary['queries_planned']} planned; {summary['queries_completed']} completed; {summary['queries_attempted']} attempted; {summary['queries_pending']} pending.",
              f"- Employer sources: {summary['sources_reached']} reached of {summary['sources_checked']} checked.",
              f"- Unique candidates: {summary['unique_candidates']}; grounded reviews: {summary['assessed']}."]
    for state,count in summary['decisions'].items(): lines.append(f'- {state}: {count}')
    lines += ['','## Decision reasons']
    for reason,count in sorted(summary['reasons'].items(),key=lambda x:-x[1]): lines.append(f'- {count}: {reason}')
    lines += ['','## Coverage and limitations']
    connected=[c for c in coverage if c['method'].startswith('Connected search:')]
    queries=sum(c['method'].count(' | ')+1 for c in connected)
    pages=[c for c in coverage if c['method']=='Connected public page retrieval']
    skipped=sum(str(c.get('error','')).startswith('Not executed:') for c in coverage)
    lines += [f'- {queries} connected-search queries across {len(connected)} saved batches.',
              f'- {len(pages)} saved public page/application retrievals recorded; their individual check dates may be older than this run.',
              f'- {skipped} selected direct queries skipped because search providers were unavailable.',
              '- Detailed per-source counts and errors are in the Search Coverage worksheet.',
              '- Search-result URLs include non-vacancy pages and documents, not just jobs.',
              '- Missing/ambiguous location, hard requirements and current application status remain holds.']
    errors=list(dict.fromkeys(str(c.get('error','')) for c in coverage if c.get('error') and not str(c.get('error','')).startswith(('Not executed:','Search-index evidence','Public page read'))))
    for error in errors[:8]: lines.append('- '+error[:300])
    md.write_text('\n'.join(lines),encoding='utf-8')
    return xlsx,md
