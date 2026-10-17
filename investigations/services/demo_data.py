import json
from datetime import datetime, timezone
from django.db import transaction
from ..models import (
    Investigation,
    InvestigationStatus,
    ResearchMode,
    ResearchRun,
    RunStatus,
    Source,
    Claim,
    ClaimEvidenceStatus,
    Entity,
    EntityType,
    EntityRelationship,
    TimelineEvent,
    ResearchReport,
)

DEMO_INVESTIGATION_ID = "00000000-0000-0000-0000-000000000001"


def seed_demo_investigation() -> Investigation:
    """
    Idempotently seeds or refreshes the curated demonstration investigation:
    'Global Advanced AI Semiconductor Supply Chain: TSMC, ASML, CoWoS Packaging, and HBM3e Bottlenecks'.
    """
    with transaction.atomic():
        # Check if already seeded
        inv, created = Investigation.objects.get_or_create(
            id=DEMO_INVESTIGATION_ID,
            defaults={
                'title': "Global Advanced AI Semiconductor Supply Chain: TSMC, ASML, CoWoS Packaging, and HBM3e Bottlenecks",
                'research_question': "Investigate the primary bottlenecks in the AI semiconductor supply chain, specifically examining TSMC advanced packaging (CoWoS), ASML High-NA lithography tools, and High-Bandwidth Memory (HBM3e/HBM4) suppliers for next-generation accelerators.",
                'status': InvestigationStatus.COMPLETED,
                'mode': ResearchMode.DEMO,
                'is_demo': True,
                'error_message': None,
            }
        )

        if not created and inv.sources.exists():
            return inv

        inv.title = "Global Advanced AI Semiconductor Supply Chain: TSMC, ASML, CoWoS Packaging, and HBM3e Bottlenecks"
        inv.research_question = "Investigate the primary bottlenecks in the AI semiconductor supply chain, specifically examining TSMC advanced packaging (CoWoS), ASML High-NA lithography tools, and High-Bandwidth Memory (HBM3e/HBM4) suppliers for next-generation accelerators."
        inv.status = InvestigationStatus.COMPLETED
        inv.mode = ResearchMode.DEMO
        inv.is_demo = True
        inv.save()

        # Clean existing related objects to ensure clean seed
        inv.sources.all().delete()
        inv.claims.all().delete()
        inv.entities.all().delete()
        inv.relationships.all().delete()
        inv.timeline_events.all().delete()
        if hasattr(inv, 'report'):
            inv.report.delete()
        inv.runs.all().delete()

        # 1. Create Initial Demo Research Run
        ResearchRun.objects.create(
            investigation=inv,
            run_number=1,
            status=RunStatus.COMPLETED,
            summary_of_changes="Initial curated baseline intelligence dataset loaded.",
            sources_found_count=6,
            claims_extracted_count=8,
            entities_discovered_count=10,
            mode_used=ResearchMode.DEMO,
            completed_at=datetime.now(timezone.utc)
        )

        # 2. Curated Sources
        s1 = Source.objects.create(
            investigation=inv,
            citation_key="S1",
            title="TSMC Q3 Earnings Call: Advanced Packaging (CoWoS) Capacity Expansion and AI Accelerator Demand",
            url="https://investor.tsmc.com/english/quarterly-results",
            source_name="TSMC Investor Relations",
            publication_date=datetime(2024, 10, 17, 12, 0, tzinfo=timezone.utc),
            excerpt="TSMC Chairman confirmed CoWoS packaging capacity will more than double in 2024 and continue aggressive expansion through 2025 to satisfy massive customer allocation backlogs for Nvidia Blackwell and AMD Instinct architectures.",
            content_hash="hash_tsmc_q3_cowos_01",
            status="VERIFIED",
            is_live=False
        )

        s2 = Source.objects.create(
            investigation=inv,
            citation_key="S2",
            title="ASML Annual Semiconductor Equipment Report: High-NA EUV Delivery Milestones and Optics Integration",
            url="https://www.asml.com/en/investors/financial-results",
            source_name="ASML Corporate Disclosures",
            publication_date=datetime(2024, 9, 25, 10, 30, tzinfo=timezone.utc),
            excerpt="ASML delivered its flagship High-NA EUV (EXE:5000, 0.55 NA) systems to Intel and TSMC pilot facilities, enabling sub-2nm process transistor scaling while managing lead times exceeding 18 months per system.",
            content_hash="hash_asml_highna_euv_02",
            status="VERIFIED",
            is_live=False
        )

        s3 = Source.objects.create(
            investigation=inv,
            citation_key="S3",
            title="SK Hynix Mass Production of 12-Layer HBM3e Memory for Next-Gen Blackwell Architecture",
            url="https://news.skhynix.com/press-releases/hbm3e-mass-production",
            source_name="SK Hynix Global Newsroom",
            publication_date=datetime(2024, 9, 26, 9, 0, tzinfo=timezone.utc),
            excerpt="SK Hynix announced world-first mass production of 36GB 12-layer HBM3e memory, securing dominant supplier share for Nvidia's GB200 NVL72 rack-scale systems through late 2025.",
            content_hash="hash_skhynix_hbm3e_03",
            status="VERIFIED",
            is_live=False
        )

        s4 = Source.objects.create(
            investigation=inv,
            citation_key="S4",
            title="Micron and Samsung Memory Qualification Reports: Yield Discrepancies in 8-Hi vs 12-Hi HBM Stacks",
            url="https://www.reuters.com/technology/semiconductors-hbm-qualifications",
            source_name="Reuters Technology Desk",
            publication_date=datetime(2024, 8, 14, 14, 15, tzinfo=timezone.utc),
            excerpt="Industry sources report Samsung Electronics encountered extended thermal and micro-bump yield qualification cycles with Nvidia for 12-layer HBM3e, while Micron secured early validation for 8-layer modules.",
            content_hash="hash_reuters_hbm_yields_04",
            status="VERIFIED",
            is_live=False
        )

        s5 = Source.objects.create(
            investigation=inv,
            citation_key="S5",
            title="TrendForce Market Analysis: 2025 AI Server Shipment Projections and CoWoS Foundry Constraints",
            url="https://www.trendforce.com/presscenter/news/2024-ai-server-cowos",
            source_name="TrendForce Semiconductor Research",
            publication_date=datetime(2024, 10, 5, 8, 0, tzinfo=timezone.utc),
            excerpt="TrendForce projects global AI server shipments to expand by over 42% in 2025. CoWoS packaging substrate availability remains the primary supply gating factor, despite aggressive OSAT subcontracting to ASE Group and Amkor.",
            content_hash="hash_trendforce_cowos_05",
            status="VERIFIED",
            is_live=False
        )

        s6 = Source.objects.create(
            investigation=inv,
            citation_key="S6",
            title="Independent OSAT Foundry Survey: Differing Forecasts on 2025 Packaging Tool Delivery Lead Times",
            url="https://www.digitimes.com/news/osat-tooling-lead-times-2024",
            source_name="DIGITIMES Research",
            publication_date=datetime(2024, 10, 11, 16, 45, tzinfo=timezone.utc),
            excerpt="Disputed forecasts emerge regarding equipment delivery: TSMC projects domestic tooling installations will resolve packaging backlogs by mid-2025, whereas OSAT subcontractors warn specialized thermocompression bonding tools face unresolved 14-month delivery queues.",
            content_hash="hash_digitimes_osat_lead_06",
            status="VERIFIED",
            is_live=False
        )

        sources_map = {"S1": s1, "S2": s2, "S3": s3, "S4": s4, "S5": s5, "S6": s6}

        # 3. Entities
        e_tsmc = Entity.objects.create(
            investigation=inv,
            name="TSMC (Taiwan Semiconductor Manufacturing Co.)",
            entity_type=EntityType.ORGANIZATION,
            description="Leading global semiconductor foundry holding over 90% market share in advanced sub-5nm AI accelerator production and proprietary CoWoS packaging."
        )
        e_tsmc.sources.set([s1, s5, s6])

        e_asml = Entity.objects.create(
            investigation=inv,
            name="ASML",
            entity_type=EntityType.ORGANIZATION,
            description="Sole global manufacturer of Extreme Ultraviolet (EUV) and High-NA lithography equipment essential for leading-edge silicon fabrication."
        )
        e_asml.sources.set([s2])

        e_nvidia = Entity.objects.create(
            investigation=inv,
            name="Nvidia",
            entity_type=EntityType.ORGANIZATION,
            description="Dominant designer of enterprise AI hardware (Hopper H100/H200, Blackwell B200, GB200 NVL72) and primary purchaser of CoWoS and HBM3e capacity."
        )
        e_nvidia.sources.set([s1, s3, s4, s5])

        e_skhynix = Entity.objects.create(
            investigation=inv,
            name="SK Hynix",
            entity_type=EntityType.ORGANIZATION,
            description="Primary supplier of High-Bandwidth Memory (HBM3 and 12-layer HBM3e) using Advanced MR-MUF packaging techniques."
        )
        e_skhynix.sources.set([s3, s4])

        e_samsung = Entity.objects.create(
            investigation=inv,
            name="Samsung Electronics",
            entity_type=EntityType.ORGANIZATION,
            description="Memory and foundry conglomerate competing with SK Hynix for HBM3e/HBM4 qualifications and offering turnkey I-Cube packaging."
        )
        e_samsung.sources.set([s4])

        e_micron = Entity.objects.create(
            investigation=inv,
            name="Micron Technology",
            entity_type=EntityType.ORGANIZATION,
            description="US-based memory fabricator producing 24GB 8-Hi HBM3e modules validated for Nvidia H200 accelerators."
        )
        e_micron.sources.set([s4])

        e_cowos = Entity.objects.create(
            investigation=inv,
            name="CoWoS (Chip-on-Wafer-on-Substrate)",
            entity_type=EntityType.TECHNOLOGY,
            description="TSMC's proprietary 2.5D advanced packaging technology that bonds compute dies and HBM stacks onto a silicon interposer."
        )
        e_cowos.sources.set([s1, s5, s6])

        e_high_na = Entity.objects.create(
            investigation=inv,
            name="High-NA EUV Lithography",
            entity_type=EntityType.TECHNOLOGY,
            description="Next-generation photolithography system with numerical aperture of 0.55 allowing 8nm critical dimension patterning."
        )
        e_high_na.sources.set([s2])

        e_blackwell = Entity.objects.create(
            investigation=inv,
            name="Nvidia Blackwell B200",
            entity_type=EntityType.PRODUCT,
            description="Dual-die GPU architecture with 208 billion transistors requiring advanced CoWoS-L packaging and 8 stacks of HBM3e memory."
        )
        e_blackwell.sources.set([s1, s3, s5])

        e_jensen = Entity.objects.create(
            investigation=inv,
            name="Jensen Huang",
            entity_type=EntityType.PERSON,
            description="CEO of Nvidia, negotiating multi-year supply allocations directly with TSMC and Korean memory foundries."
        )
        e_jensen.sources.set([s1, s3])

        # 4. Relationships
        EntityRelationship.objects.create(
            investigation=inv,
            source_entity=e_asml,
            target_entity=e_tsmc,
            relation_type="SUPPLIES_LITHOGRAPHY_EQUIPMENT",
            description="ASML provides critical Low-NA and High-NA EUV scanners required for TSMC 3nm and 2nm production nodes [S2].",
            evidence_source=s2,
            is_inference=False
        )
        EntityRelationship.objects.create(
            investigation=inv,
            source_entity=e_tsmc,
            target_entity=e_nvidia,
            relation_type="FOUNDRY_AND_COWOS_PACKAGING_PARTNER",
            description="TSMC fabricates all Blackwell silicon dies and executes 2.5D CoWoS-L packaging [S1, S5].",
            evidence_source=s1,
            is_inference=False
        )
        EntityRelationship.objects.create(
            investigation=inv,
            source_entity=e_skhynix,
            target_entity=e_nvidia,
            relation_type="PRIMARY_HBM3E_SUPPLIER",
            description="SK Hynix supplies over 70% of 12-layer HBM3e memory stacks for GB200 accelerators [S3].",
            evidence_source=s3,
            is_inference=False
        )
        EntityRelationship.objects.create(
            investigation=inv,
            source_entity=e_samsung,
            target_entity=e_skhynix,
            relation_type="COMPETES_FOR_HBM_MARKET_SHARE",
            description="Samsung actively competes to qualify 12-layer HBM3e while developing integrated turnkey HBM4 solutions [S4].",
            evidence_source=s4,
            is_inference=False
        )
        EntityRelationship.objects.create(
            investigation=inv,
            source_entity=e_cowos,
            target_entity=e_blackwell,
            relation_type="CRITICAL_MANUFACTURING_DEPENDENCY",
            description="Blackwell B200 accelerators cannot be produced without TSMC CoWoS-L packaging, making substrate volume the chief bottleneck [S1, S5].",
            evidence_source=s5,
            is_inference=False
        )
        EntityRelationship.objects.create(
            investigation=inv,
            source_entity=e_jensen,
            target_entity=e_nvidia,
            relation_type="EXECUTIVE_LEADERSHIP",
            description="Jensen Huang directs hardware architectural roadmaps and supply agreements [S1, S3].",
            evidence_source=s1,
            is_inference=False
        )

        # 5. Claims with Corroboration & Disagreements
        c1 = Claim.objects.create(
            investigation=inv,
            claim_text="TSMC CoWoS advanced packaging capacity is doubling in 2024 and expanding to approximately 35,000–40,000 wafers per month by late 2025 to alleviate AI accelerator delivery constraints.",
            evidence_status=ClaimEvidenceStatus.SUPPORTED,
            confidence_assessment="Multi-source corroborated by TSMC official quarterly earnings and TrendForce semiconductor market analyses.",
            dispute_reason=None
        )
        c1.sources.set([s1, s5])

        c2 = Claim.objects.create(
            investigation=inv,
            claim_text="SK Hynix commenced mass production of 12-layer 36GB HBM3e memory, establishing primary volume supplier status for Nvidia Blackwell GB200 systems.",
            evidence_status=ClaimEvidenceStatus.SUPPORTED,
            confidence_assessment="Corroborated across corporate announcement and industry supply chain reports.",
            dispute_reason=None
        )
        c2.sources.set([s3, s4])

        c3 = Claim.objects.create(
            investigation=inv,
            claim_text="ASML High-NA EUV lithography systems (EXE:5000) have entered pilot integration phases with lead times surpassing 18 months per scanner.",
            evidence_status=ClaimEvidenceStatus.SINGLE_SOURCE,
            confidence_assessment="Single primary manufacturer corporate disclosure (ASML Corporate Disclosures).",
            dispute_reason=None
        )
        c3.sources.set([s2])

        c4 = Claim.objects.create(
            investigation=inv,
            claim_text="Timeline for resolving CoWoS packaging backlogs: TSMC projects internal capacity expansion will satisfy peak demand by mid-2025, whereas OSAT subcontractors warn tool delivery bottlenecks will extend shortages through late 2025.",
            evidence_status=ClaimEvidenceStatus.DISPUTED,
            confidence_assessment="Competing forecasts: TSMC leadership outlook versus independent packaging equipment delivery timelines.",
            dispute_reason="TSMC reports aggressive domestic facility ramp-ups [S1], but independent packaging subcontractors report extended 14-month equipment queues for advanced thermocompression bonders [S6]."
        )
        c4.sources.set([s1, s6])

        c5 = Claim.objects.create(
            investigation=inv,
            claim_text="Samsung Electronics experienced delayed validation for its 12-layer HBM3e memory with Nvidia due to thermal dissipation and microbump yield challenges.",
            evidence_status=ClaimEvidenceStatus.UNVERIFIED,
            confidence_assessment="Unverified industry reports; Samsung has not publicly confirmed specific customer qualification timeline delays.",
            dispute_reason="Reported by Reuters sources [S4] but not officially confirmed by Samsung Electronics."
        )
        c5.sources.set([s4])

        # 6. Timeline Events
        TimelineEvent.objects.create(
            investigation=inv,
            event_date="August 2024",
            title="HBM3e Qualification Split",
            description="Reports surface regarding differing yield rates between Micron 8-Hi modules and Samsung 12-Hi test stacks [S4].",
            source=s4
        )
        TimelineEvent.objects.create(
            investigation=inv,
            event_date="September 2024",
            title="ASML High-NA Milestone & SK Hynix 12-Hi Mass Production",
            description="ASML confirms initial pilot shipments of High-NA EUV scanners [S2], while SK Hynix begins volume production of 36GB 12-layer HBM3e [S3].",
            source=s3
        )
        TimelineEvent.objects.create(
            investigation=inv,
            event_date="October 2024",
            title="TSMC CoWoS Doubling & Capacity Allocation Outlook",
            description="TSMC confirms aggressive packaging capacity doubling while conflicting equipment lead-time reports emerge from OSAT subcontractors [S1, S6].",
            source=s1
        )
        TimelineEvent.objects.create(
            investigation=inv,
            event_date="2025 Projected",
            title="GB200 NVL72 Volume Deliveries",
            description="Nvidia Blackwell rack-scale servers scale production contingent on resolved packaging substrates and 12-layer memory supply [S3, S5].",
            source=s5
        )

        # 7. Synthesized Research Report
        key_findings = [
            "CoWoS packaging remains the acute physical bottleneck: Despite TSMC doubling packaging throughput in 2024 [S1], AI server shipment demand projected at +42% in 2025 continues to outstrip available packaging capacity [S5].",
            "High-Bandwidth Memory tier consolidation: SK Hynix maintains a clear lead in 12-layer HBM3e mass production [S3], while Samsung's prolonged qualification tests have created near-term supplier concentration risks [S4].",
            "Conflicting equipment resolution timelines: TSMC projects internal tool installations will ease packaging constraints by mid-2025 [S1], whereas OSAT subcontractors warn 14-month thermocompression tooling lead times may prolong constraints [S6].",
            "Lithography roadmaps are stable for sub-2nm nodes: ASML High-NA EUV tools are on schedule for pilot R&D, meaning front-end lithography is not currently gating near-term Blackwell volume [S2]."
        ]

        ResearchReport.objects.create(
            investigation=inv,
            topic_primer=(
                "### 1. Foundational Definition & Problem Statement\n"
                "Modern Artificial Intelligence accelerators (such as Nvidia Blackwell B200 and AMD MI300X) are not single monolithic silicon chips. "
                "Because frontier AI models require trillions of floating-point calculations every second, a single silicon die is too small and too slow "
                "to handle the workload. Instead, modern AI hardware relies on **heterogeneous multi-die packaging**: stitching compute dies together with "
                "vertical stacks of ultra-fast memory [S1, S3]. The AI chip bottleneck is no longer just about printing transistors, but physically connecting "
                "and cooling them.\n\n"
                "### 2. Core Architecture & Operating Principles (How It Works)\n"
                "- **Compute Dies (Front-End Silicon)**: Massive logic dies containing over 100 to 200 billion transistors, fabricated at leading-edge nodes (3nm/2nm) using ASML's Extreme Ultraviolet (EUV) light scanners [S2].\n"
                "- **The 'Memory Wall' & HBM (High-Bandwidth Memory)**: Standard computer memory (DDR5) sits inches away across a printed circuit board, creating high latency. HBM solves this by stacking DRAM chips vertically (8 or 12 layers high) directly beside the processor, interconnected with microscopic microscopic Through-Silicon Vias (TSVs) [S3, S4].\n"
                "- **Advanced Packaging (TSMC CoWoS)**: 'Chip-on-Wafer-on-Substrate' places the processor dies and the HBM stacks onto a microscopic silicon bridge called an interposer. This allows thousands of microscopic wiring lanes to transmit petabytes of data per second with minimal power dissipation [S1, S5].\n\n"
                "### 3. Key Terminology Primer (Glossary)\n"
                "- **CoWoS (Chip-on-Wafer-on-Substrate)**: TSMC's proprietary 2.5D packaging system. Currently the #1 physical bottleneck in AI hardware delivery.\n"
                "- **HBM3e / HBM4**: The newest generations of High-Bandwidth Memory (36GB capacity per 12-layer stack).\n"
                "- **EUV Lithography**: Photolithography machines built exclusively by ASML using 13.5nm wavelength light to pattern silicon wafers.\n"
                "- **OSAT**: Outsourced Semiconductor Assembly and Test houses (e.g. Amkor, ASE) that package chips after raw wafer fabrication.\n\n"
                "### 4. Strategic Importance\n"
                "Whoever controls packaging capacity controls the pacing of global AI deployment. Even if a foundry prints millions of silicon dies, "
                "none of them can be sold as functional AI superchips without CoWoS packaging substrate and certified 12-layer HBM stacks [S1, S5]."
            ),
            executive_summary=(
                "This intelligence investigation assesses the critical supply chain nodes enabling next-generation "
                "artificial intelligence accelerators. Analysis of verified primary corporate disclosures [S1, S2, S3] "
                "and independent semiconductor research [S4, S5, S6] demonstrates that compute die fabrication is no "
                "longer the primary constraint. Instead, structural capacity gating centers on 2.5D advanced packaging "
                "(TSMC CoWoS) [S1, S5] and multi-layer High-Bandwidth Memory (HBM3e) thermal yield qualification [S3, S4]. "
                "While ASML lithography progress remains secure [S2], conflicting timelines persist between TSMC's "
                "optimistic capacity guidance and independent OSAT tool delivery warnings [S1, S6]."
            ),
            key_findings=json.dumps(key_findings),
            supporting_evidence_synthesis=(
                "1. Advanced Packaging Capacity Constraints: TSMC's proprietary Chip-on-Wafer-on-Substrate (CoWoS) "
                "technology is indispensable for interconnecting compute silicon with HBM modules [S1]. Demand driven "
                "by Nvidia Blackwell B200 and AMD Instinct architectures has forced TSMC to outsource secondary packaging "
                "steps to OSAT partners such as ASE and Amkor [S5].\n\n"
                "2. Memory Hierarchy Dynamics: Next-generation architectures demand 12-layer HBM3e providing up to "
                "36GB per stack [S3]. SK Hynix has captured dominant allocation through proven Mass Reflow Molded Underfill "
                "(MR-MUF) yields [S3], whereas Samsung's reliance on non-conductive film (NCF) prompted extended thermal "
                "qualification reviews [S4].\n\n"
                "3. Front-End vs Back-End Divergence: Extreme Ultraviolet (EUV) photolithography from ASML represents an "
                "orderly technological transition [S2], contrasting sharply with the back-end packaging deficit where "
                "physical cleanroom floor space and specialized bonding tools remain scarce [S5, S6]."
            ),
            contradictions_and_disagreements=(
                "Disputed Assessment — Timeline for Packaging Relief:\n"
                "- Source [S1] (TSMC Management): Projects domestic CoWoS production capacity will surpass 35,000 "
                "wafers per month by mid-2025, substantially alleviating hardware backlogs.\n"
                "- Source [S6] (DIGITIMES / OSAT Survey): Reports specialized thermocompression bonders and laser debonding "
                "equipment face backlogged delivery times exceeding 14 months, indicating shortages may persist throughout 2025."
            ),
            unresolved_questions=(
                "1. Will Samsung Electronics secure formal volume qualification from Nvidia for 12-layer HBM3e prior to H2 2025?\n"
                "2. Can TSMC successfully ramp CoWoS-L wafer yields at its Chiayi Advanced Packaging Park without tool delivery slips?\n"
                "3. What portion of HBM4 base-die fabrication will migrate from traditional memory processes to TSMC leading-edge logic?"
            ),
            further_research_directions=(
                "1. Monitor upcoming quarterly earnings filings from ASML, TSMC, and SK Hynix for updated capital expenditure guidance.\n"
                "2. Track customer allocation reports for Nvidia GB200 NVL72 server rack shipments.\n"
                "3. Cross-examine HBM4 JEDEC standard finalization regarding base-die logic specifications."
            ),
            generated_by_mode=ResearchMode.DEMO
        )

        return inv
