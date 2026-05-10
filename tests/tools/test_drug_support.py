from biotarget_scout.models.schemas import EntityResult, KGResult, LiteratureResult, PubMedPaper
from biotarget_scout.tools import drug_support


def test_extract_drug_candidates_from_abstract():
    text = "Patients received evolocumab (Repatha) with statin therapy."
    ent = EntityResult(chemicals=["aspirin"])
    names = drug_support.extract_drug_candidates(text, ent)
    lower = {n.lower() for n in names}
    assert "evolocumab" in lower
    assert "repatha" in lower


def test_merge_literature_drugs_into_kg():
    kg = KGResult(existing_drugs=[], omim_hits=1)
    lit = LiteratureResult(
        papers=[PubMedPaper(pmid="1", title="PCSK9 trial", abstract="Alirocumab reduced LDL.")],
        entities=EntityResult(),
    )
    out = drug_support.merge_literature_drugs_into_kg(kg, lit)
    assert "alirocumab" in [d.lower() for d in out.existing_drugs]
