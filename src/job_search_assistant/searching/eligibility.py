"""Conservative eligibility; missing evidence never becomes permission."""
import re


def location_gate(text, location=''):
    text = (location + '\n' + text).casefold()
    if re.search(r'(?:cannot|unable to|do not|not able to) (?:hire|employ).{0,60}(?:nova scotia|halifax)|(?:excluding|except|not including) nova scotia', text):
        return 'ineligible', 'Employer explicitly excludes Nova Scotia'
    scope=re.search(r'(?:must be based in(?: either)?|only accepting applicants from(?: the provinces of)?) ([^.!\n]{1,220})',text)
    if scope and scope[1].startswith(('alberta','british columbia','ontario','quebec','qu\u00e9bec')) and not re.search(r'nova scotia|halifax',scope[1]):
        return 'ineligible','Explicit permitted-province list excludes Nova Scotia'
    if re.search(r'(?:must|require[ds]?) (?:to )?relocat', text):
        return 'ineligible', 'Relocation required'
    if re.search(r'(?:us|u\.s\.|united states)[ -]only|only (?:in|within) (?:the )?(?:us|united states)', text):
        return 'ineligible', 'US-only role'
    if re.search(r'(?:must|require[ds]?|minimum|at least).{0,90}(?:office|onsite|on-site|hybrid).{0,90}(?:toronto|montreal|ottawa|vancouver)', text):
        return 'ineligible', 'Required attendance outside Halifax'
    if re.search(r'remote.{0,25}(?:ontario|british columbia|quebec).{0,15}only|only.{0,60}(?:ontario|british columbia|qu(?:e|\u00e9)bec)|must be based in (?:either )?(?:alberta|british columbia|ontario).{0,100}aren.t able to hire', text):
        return 'ineligible', 'Remote restricted to other provinces'
    if 'halifax' in text and re.search(r'on.?site|hybrid',text):
        return 'eligible', 'Halifax attendance allowed'
    if re.search(r'anywhere (?:in|within|across) canada|all (?:canadian )?provinces|remote.{0,25}canada|canada.{0,25}remote', text):
        # A remote city-specific label alone cannot establish nationwide hiring.
        if re.search(r'remote.{0,15}(?:ontario|toronto|vancouver|montreal|ottawa)|(?:toronto|vancouver).{0,12}remote', location.casefold()):
            return 'unknown', 'City/province-specific remote label; Nova Scotia eligibility unresolved'
        return 'eligible', 'Remote Canada stated; review full posting for provincial restrictions'
    return 'unknown', 'Canadian / Nova Scotia eligibility not established'


def title_gate(title):
    # Routing only; full responsibilities/requirements decide suitability later.
    if re.search(r'\b(?:chief|cto|vice president|vp of engineering|sales manager|customer success|account executive)\b',title,re.I):
        return False
    if re.search(r'\bAI Enablement Lead\b|\b(?:project|program(?:me)?|delivery|change) manager\b',title,re.I):
        return True
    terms=r'engineering|software|development|platform|infrastructure|backend|data|technical|technology|agile|delivery|change|cloud|developer|devops|reliability|\bit\b|\bsre\b'
    return bool(re.search(r'(?:'+terms+r').*(?:manager|director|head|lead)|(?:manager|director|head).*(?:'+terms+r')',title,re.I))
