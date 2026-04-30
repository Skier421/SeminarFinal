"""
Local historical headlines for the simulator.
"""

HEADLINES = [
    {
        'year': 1914,
        'headline': 'World War I begins after tensions in Europe erupt into full-scale conflict.',
        'source': 'Historical Archive',
        'url': 'https://en.wikipedia.org/wiki/World_War_I'
    },
    {
        'year': 1918,
        'headline': 'World War I ends as the armistice is signed on November 11.',
        'source': 'Historical Archive',
        'url': 'https://en.wikipedia.org/wiki/Armistice_of_11_November_1918'
    },
    {
        'year': 1929,
        'headline': 'Wall Street crashes, triggering the Great Depression.',
        'source': 'Historical Archive',
        'url': 'https://en.wikipedia.org/wiki/Wall_Street_Crash_of_1929'
    },
    {
        'year': 1939,
        'headline': 'World War II begins with the invasion of Poland.',
        'source': 'Historical Archive',
        'url': 'https://en.wikipedia.org/wiki/Invasion_of_Poland'
    },
    {
        'year': 1945,
        'headline': 'World War II ends after Allied victory in Europe and the Pacific.',
        'source': 'Historical Archive',
        'url': 'https://en.wikipedia.org/wiki/End_of_World_War_II'
    },
    {
        'year': 1957,
        'headline': 'Soviet Union launches Sputnik, opening the Space Age.',
        'source': 'Historical Archive',
        'url': 'https://en.wikipedia.org/wiki/Sputnik_1'
    },
    {
        'year': 1963,
        'headline': 'President John F. Kennedy is assassinated in Dallas.',
        'source': 'Historical Archive',
        'url': 'https://en.wikipedia.org/wiki/Assassination_of_John_F._Kennedy'
    },
    {
        'year': 1969,
        'headline': 'Apollo 11 lands on the Moon; humans walk on the lunar surface.',
        'source': 'Historical Archive',
        'url': 'https://en.wikipedia.org/wiki/Apollo_11'
    },
    {
        'year': 1973,
        'headline': 'Oil embargo shocks global markets and fuels inflation.',
        'source': 'Historical Archive',
        'url': 'https://en.wikipedia.org/wiki/1973_oil_crisis'
    },
    {
        'year': 1986,
        'headline': 'Chernobyl nuclear disaster raises worldwide safety concerns.',
        'source': 'Historical Archive',
        'url': 'https://en.wikipedia.org/wiki/Chernobyl_disaster'
    },
    {
        'year': 1989,
        'headline': 'The Berlin Wall falls, signaling the end of the Cold War era.',
        'source': 'Historical Archive',
        'url': 'https://en.wikipedia.org/wiki/Fall_of_the_Berlin_Wall'
    },
    {
        'year': 1991,
        'headline': 'The Soviet Union dissolves, reshaping global geopolitics.',
        'source': 'Historical Archive',
        'url': 'https://en.wikipedia.org/wiki/Dissolution_of_the_Soviet_Union'
    },
    {
        'year': 2001,
        'headline': 'September 11 attacks profoundly change global security policy.',
        'source': 'Historical Archive',
        'url': 'https://en.wikipedia.org/wiki/September_11_attacks'
    },
    {
        'year': 2008,
        'headline': 'Global financial crisis deepens after major banking failures.',
        'source': 'Historical Archive',
        'url': 'https://en.wikipedia.org/wiki/Financial_crisis_of_2007%E2%80%932008'
    },
    {
        'year': 2020,
        'headline': 'COVID-19 pandemic disrupts economies and daily life worldwide.',
        'source': 'Historical Archive',
        'url': 'https://en.wikipedia.org/wiki/COVID-19_pandemic'
    }
]


def get_headline_for_year(year: int):
    """Return the configured headline for an exact year match."""
    for item in HEADLINES:
        if item['year'] == year:
            return item
    return None
