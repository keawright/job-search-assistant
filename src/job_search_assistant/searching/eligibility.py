"""Conservative eligibility; missing evidence never becomes permission."""
import re


def location_gate(text, location=''):
    # Structured vacancy locations are stronger than company-wide boilerplate.
    foreign = r'spain|poland|united states|\bus\b|\busa\b|u\.s\.|united kingdom|\buk\b|germany|france|ireland|netherlands|portugal|italy|romania|sweden|switzerland|australia|india|singapore|brazil|mexico|south africa|philippines|japan|europe|emea|apac|latin america|latam|new zealand|finland|norway|denmark|austria|belgium|czechia|czech republic|hungary|greece|pakistan|argentina|colombia|chile|israel|turkey|t\u00fcrkiye|estonia|lithuania|latvia|ukraine|taiwan|china|hong kong|south korea|united arab emirates|\buae\b|malaysia|indonesia|vietnam|thailand|egypt|nigeria|kenya'
    label = location.casefold()
    if re.search(r'\b(?:hybrid|on.?site)\b', label) and re.search(r'toronto|montreal|montr\u00e9al|ottawa|vancouver|calgary|edmonton|winnipeg',label) and not re.search(r'halifax|nova scotia',label):
        return 'ineligible', 'Required office location is outside Halifax: ' + location
    if (re.search(foreign, label) and not re.search(r'\bcanada\b|\bcanadian\b|\bhalifax\b|\bnova scotia\b|worldwide|anywhere in the world|global|north america', label)):
        return 'ineligible', 'Vacancy location is outside Canada: ' + location
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
    if re.search(r'\b(?:associate )?director\b', title, re.I) and not re.search(r'\b(?:sales|marketing|creative|art director|account director)\b',title,re.I):
        return True
    # Lead/staff/senior engineering titles alone are individual-contributor roles.
    if re.search(r'\b(?:software|security|platform|data|infrastructure|backend|frontend|devops|site reliability) engineer\b',title,re.I) and not re.search(r'\bmanager\b|\bdirector\b|\bhead\b',title,re.I):
        return False
    terms=r'engineering|software|development|platform|infrastructure|backend|data|technical|technology|agile|delivery|change|cloud|developer|devops|reliability|\bit\b|\bsre\b'
    return bool(re.search(r'(?:'+terms+r').*(?:manager|director|head|lead)|(?:manager|director|head).*(?:'+terms+r')',title,re.I))


def exclusion_reason(posting):
    """Hard role/location gates also apply to uncertain duplicates and old reports."""
    if posting.title not in {'', 'page_title', 'Jobs'} and not title_gate(posting.title):
        return 'Outside target leadership, change, delivery, project and program roles: ' + posting.title
    location, reason = location_gate(posting.description, posting.location)
    return reason if location == 'ineligible' else ''
