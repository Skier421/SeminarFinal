"""
Hardcoded historical headlines for classroom use.
At least one major event per decade from 1920 to 2020.
"""

HEADLINES_BY_YEAR = {
    1929: "Wall Street crashes, triggering the Great Depression.",
    1930: "Stocks keep tumbling as the U.S. economy struggles with the Great Depression.",
    1931: "Unemployment rises sharply as banks fail across the country.",
    1932: "Franklin D. Roosevelt wins the presidency amid economic turmoil.",
    1933: "New Deal programs launch to stabilize the economy and support workers.",
    1934: "Financial reforms create the SEC and strengthen investor protections.",
    1935: "Social Security Act signed into law to aid retirees and unemployed workers.",
    1936: "Economic growth returns slowly as recovery policies continue.",
    1937: "A recession returns as production slows and unemployment spikes again.",
    1938: "Recovery resumes after corrective fiscal action and banking stabilization.",
    1939: "World War II begins with Germany's invasion of Poland.",
    1940: "Europe is engulfed in war while U.S. industry ramps up production.",
    1941: "The attack on Pearl Harbor draws America into World War II.",
    1942: "War production surges as the U.S. mobilizes for the global conflict.",
    1943: "Allied forces gain momentum across multiple fronts.",
    1944: "D-Day invasion marks a turning point in the war against Nazi Germany.",
    1945: "World War II ends after Allied victory in Europe and the Pacific.",
    1957: "Soviet Union launches Sputnik, marking the start of the Space Age.",
    1969: "Apollo 11 lands on the Moon and humans walk on its surface.",
    1973: "Oil embargo shocks global markets and accelerates inflation.",
    1989: "The Berlin Wall falls, signaling a major Cold War turning point.",
    1991: "The Soviet Union dissolves, reshaping global politics.",
    2001: "September 11 attacks transform global security policy.",
    2008: "Global financial crisis deepens after major banking failures.",
    2020: "COVID-19 pandemic disrupts economies and daily life worldwide."
}


def get_headline_for_year(year: int) -> str:
    """Return the best available headline for a given year."""
    if year in HEADLINES_BY_YEAR:
        return HEADLINES_BY_YEAR[year]

    # Prefer the closest year before the current date.
    available_years = sorted(HEADLINES_BY_YEAR.keys())
    nearest_year = None
    for y in available_years:
        if y <= year:
            nearest_year = y
        else:
            break

    if nearest_year is not None:
        return HEADLINES_BY_YEAR[nearest_year]

    # Fallback to the earliest known headline
    return HEADLINES_BY_YEAR.get(available_years[0], 'Historical headline unavailable.')
