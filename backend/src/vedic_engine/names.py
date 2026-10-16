"""Nakshatra-pada name syllables, the standard 108-entry table (spec 5.12).

Sources (retrieved 2026-10-17; not typed from memory, extracted from the pages):

* Devanagari: OnlineJyotish, Hindi astrology lesson 3, "नक्षत्र चरणों के अनुसार नामाक्षर तालिका"
  (https://www.onlinejyotish.com/hindi-astrology/astrology-lessons/lesson_3.php), which cites
  the Laghu Brahmayamalam.
* Latin: Dekho Panchang, "Nakshatra Pada" (https://dekhopanchang.com/learn/nakshatra-pada),
  which attributes the table to the Muhurta Chintamani.

The two agree on every syllable except two regional variants, where the Latin is taken as
the transliteration of the Devanagari so that each pair names one sound (both variants are
listed together, e.g. "Ju/Khi", in the English Wikipedia "Nakshatra" pada table):

* Ardra pada 4: छ "Chha" (Dekho Panchang: "Na").
* Shravana padas 1-4: खी खू खे खो "Khi Khu Khe Kho" (Dekho Panchang: "Ju Je Jo Gha").

Spec section 1, correction 4: Punarvasu = Ke, Ko, Ha, Hi; "Ra" is Chitra pada 3.
"""

# SYLLABLES[nakshatra 0-26][pada 1-4 minus 1] = (Latin, Devanagari)
SYLLABLES: tuple[tuple[tuple[str, str], ...], ...] = (
    (("Chu", "चु"), ("Che", "चे"), ("Cho", "चो"), ("La", "ला")),  # ashwini
    (("Lee", "ली"), ("Lu", "लू"), ("Le", "ले"), ("Lo", "लो")),  # bharani
    (("A", "आ"), ("I", "ई"), ("U", "ऊ"), ("E", "ए")),  # krittika
    (("O", "ओ"), ("Va", "वा"), ("Vi", "वी"), ("Vu", "वु")),  # rohini
    (("Ve", "वे"), ("Vo", "वो"), ("Ka", "का"), ("Ki", "की")),  # mrigashira
    (("Ku", "कु"), ("Gha", "घ"), ("Ng", "ङ"), ("Chha", "छ")),  # ardra
    (("Ke", "के"), ("Ko", "को"), ("Ha", "हा"), ("Hi", "ही")),  # punarvasu
    (("Hu", "हु"), ("He", "हे"), ("Ho", "हो"), ("Da", "डा")),  # pushya
    (("Di", "डी"), ("Du", "डू"), ("De", "डे"), ("Do", "डो")),  # ashlesha
    (("Ma", "मा"), ("Mi", "मी"), ("Mu", "मू"), ("Me", "मे")),  # magha
    (("Mo", "मो"), ("Ta", "टा"), ("Ti", "टी"), ("Tu", "टू")),  # purva_phalguni
    (("Te", "टे"), ("To", "टो"), ("Pa", "पा"), ("Pi", "पी")),  # uttara_phalguni
    (("Pu", "पू"), ("Sha", "ष"), ("Na", "ण"), ("Tha", "ठ")),  # hasta
    (("Pe", "पे"), ("Po", "पो"), ("Ra", "रा"), ("Ri", "री")),  # chitra
    (("Ru", "रू"), ("Re", "रे"), ("Ro", "रो"), ("Ta", "ता")),  # swati
    (("Ti", "ती"), ("Tu", "तू"), ("Te", "ते"), ("To", "तो")),  # vishakha
    (("Na", "ना"), ("Ni", "नी"), ("Nu", "नू"), ("Ne", "ने")),  # anuradha
    (("No", "नो"), ("Ya", "या"), ("Yi", "यी"), ("Yu", "यू")),  # jyeshtha
    (("Ye", "ये"), ("Yo", "यो"), ("Bha", "भा"), ("Bhi", "भी")),  # mula
    (("Bhu", "भू"), ("Dha", "धा"), ("Pha", "फा"), ("Dha", "ढा")),  # purva_ashadha
    (("Bhe", "भे"), ("Bho", "भो"), ("Ja", "जा"), ("Ji", "जी")),  # uttara_ashadha
    (("Khi", "खी"), ("Khu", "खू"), ("Khe", "खे"), ("Kho", "खो")),  # shravana
    (("Ga", "गा"), ("Gi", "गी"), ("Gu", "गू"), ("Ge", "गे")),  # dhanishta
    (("Go", "गो"), ("Sa", "सा"), ("Si", "सी"), ("Su", "सू")),  # shatabhisha
    (("Se", "से"), ("So", "सो"), ("Da", "दा"), ("Di", "दी")),  # purva_bhadrapada
    (("Du", "दू"), ("Tha", "थ"), ("Jha", "झ"), ("Jna", "ञ")),  # uttara_bhadrapada
    (("De", "दे"), ("Do", "दो"), ("Cha", "चा"), ("Chi", "ची")),  # revati
)


def syllable(nak: int, pada: int) -> tuple[str, str]:
    """(Latin, Devanagari) name syllable of nakshatra ``nak`` (0-26), ``pada`` (1-4)."""
    if not 0 <= nak <= 26 or not 1 <= pada <= 4:
        raise ValueError(f"nakshatra must be 0-26 and pada 1-4, got {nak}, {pada}")
    return SYLLABLES[nak][pada - 1]
