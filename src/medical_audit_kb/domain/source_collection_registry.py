from __future__ import annotations

from dataclasses import dataclass

from medical_audit_kb.domain.constants import SourceCollection

KNOWLEDGE_QUERY_CONTRACT_VERSION = "knowledge-query-contract-v2"


@dataclass(frozen=True, slots=True)
class SourceCollectionDefinition:
    collection: SourceCollection
    label: str
    scope: str
    phase: str
    domain: str
    evidence_group: str
    description: str
    audit_hint: str
    product_queryable: bool = True

    def to_contract_payload(self) -> dict[str, object]:
        return {
            "value": self.collection.value,
            "label": self.label,
            "scope": self.scope,
            "phase": self.phase,
            "domain": self.domain,
            "evidence_group": self.evidence_group,
            "description": self.description,
            "audit_hint": self.audit_hint,
            "product_queryable": self.product_queryable,
        }


SOURCE_COLLECTION_DEFINITIONS: tuple[SourceCollectionDefinition, ...] = (
    SourceCollectionDefinition(
        collection=SourceCollection.MEDICAL_INSURANCE_LAWS,
        label="法规政策",
        scope="公开知识库",
        phase="P6A-medical-current-library-completion",
        domain="medical",
        evidence_group="legal",
        description="医保、医疗、药品、基金监管相关法律政策。",
        audit_hint="用于判断制度依据和监管边界。",
    ),
    SourceCollectionDefinition(
        collection=SourceCollection.SUPERVISION_RULES_KNOWLEDGE,
        label="监管两库",
        scope="系统知识库",
        phase="P6A-medical-current-library-completion",
        domain="medical",
        evidence_group="rule",
        description="智能监管规则库、知识库和知识点明细。",
        audit_hint="用于定位规则口径和疑点类型。",
    ),
    SourceCollectionDefinition(
        collection=SourceCollection.MEDICAL_INSURANCE_CATALOG,
        label="医保目录",
        scope="系统知识库",
        phase="P6A-medical-current-library-completion",
        domain="medical",
        evidence_group="catalog",
        description="药品、诊疗项目、编码、支付范围和限制条件。",
        audit_hint="用于核验目录编码、剂型、支付限制。",
    ),
    SourceCollectionDefinition(
        collection=SourceCollection.RISK_NEGATIVE_LIST,
        label="风险清单",
        scope="系统知识库",
        phase="P6A-medical-current-library-completion",
        domain="medical",
        evidence_group="risk",
        description="高风险负面清单、案例和风险线索。",
        audit_hint="用于辅助排查异常模式。",
    ),
    SourceCollectionDefinition(
        collection=SourceCollection.POLICY_GENERAL_POLICY,
        label="综合政策与规范性文件",
        scope="P6B 政策知识库",
        phase="P6B-policy-library-buildout",
        domain="policy",
        evidence_group="policy",
        description="综合政策、规范性文件和通用治理要求。",
        audit_hint="用于补充跨业务政策口径。",
    ),
    SourceCollectionDefinition(
        collection=SourceCollection.POLICY_FINANCE_PRICE_PROCUREMENT,
        label="财政价格与采购政策",
        scope="P6B 政策知识库",
        phase="P6B-policy-library-buildout",
        domain="policy",
        evidence_group="policy",
        description="财政、价格、采购和资金管理相关政策。",
        audit_hint="用于核验价格、采购和财政资金依据。",
    ),
    SourceCollectionDefinition(
        collection=SourceCollection.POLICY_DATA_STATISTICS_DISCLOSURE,
        label="数据统计与政务公开",
        scope="P6B 政策知识库",
        phase="P6B-policy-library-buildout",
        domain="policy",
        evidence_group="policy",
        description="数据统计、信息公开和政务公开相关文件。",
        audit_hint="用于核对披露、统计和数据口径。",
    ),
    SourceCollectionDefinition(
        collection=SourceCollection.POLICY_REFORM_PILOT,
        label="规划改革与试点方案",
        scope="P6B 政策知识库",
        phase="P6B-policy-library-buildout",
        domain="policy",
        evidence_group="policy",
        description="改革、试点、规划和专项方案。",
        audit_hint="用于判断试点边界和阶段性要求。",
    ),
    SourceCollectionDefinition(
        collection=SourceCollection.POLICY_SOCIAL_SECURITY_LIVELIHOOD,
        label="社会保障与民生政策",
        scope="P6B 政策知识库",
        phase="P6B-policy-library-buildout",
        domain="policy",
        evidence_group="policy",
        description="社保、民生保障和公共服务政策。",
        audit_hint="用于补充民生政策适用条件。",
    ),
    SourceCollectionDefinition(
        collection=SourceCollection.POLICY_INDUSTRY_BUSINESS_ENVIRONMENT,
        label="产业发展与营商环境",
        scope="P6B 政策知识库",
        phase="P6B-policy-library-buildout",
        domain="policy",
        evidence_group="policy",
        description="产业发展、营商环境和市场主体政策。",
        audit_hint="用于核对产业和经营环境政策依据。",
    ),
    SourceCollectionDefinition(
        collection=SourceCollection.MANAGEMENT_ORG_PERSONNEL_QUALIFICATION,
        label="机构人员与资质管理",
        scope="P6C 管理知识库",
        phase="P6C-management-library-buildout",
        domain="management",
        evidence_group="management",
        description="机构设置、人员管理和资质资格要求。",
        audit_hint="用于核验主体、人员和资质合规性。",
    ),
    SourceCollectionDefinition(
        collection=SourceCollection.MANAGEMENT_MARKET_QUALITY,
        label="市场监管与质量管理",
        scope="P6C 管理知识库",
        phase="P6C-management-library-buildout",
        domain="management",
        evidence_group="management",
        description="市场监管、质量监督和标准管理要求。",
        audit_hint="用于核验市场质量监管口径。",
    ),
    SourceCollectionDefinition(
        collection=SourceCollection.MANAGEMENT_LICENSE_ENFORCEMENT,
        label="行政许可与监督执法",
        scope="P6C 管理知识库",
        phase="P6C-management-library-buildout",
        domain="management",
        evidence_group="management",
        description="行政许可、监督执法和处罚程序。",
        audit_hint="用于判断许可、检查和执法程序依据。",
    ),
    SourceCollectionDefinition(
        collection=SourceCollection.MANAGEMENT_SAFETY_EMERGENCY,
        label="安全生产与应急管理",
        scope="P6C 管理知识库",
        phase="P6C-management-library-buildout",
        domain="management",
        evidence_group="management",
        description="安全生产、应急管理和风险防控要求。",
        audit_hint="用于核验安全和应急管理责任。",
    ),
    SourceCollectionDefinition(
        collection=SourceCollection.MANAGEMENT_JUDICIAL_AUDIT_PROCEDURE,
        label="司法审计与程序管理",
        scope="P6C 管理知识库",
        phase="P6C-management-library-buildout",
        domain="management",
        evidence_group="management",
        description="司法、审计、程序和监督管理文件。",
        audit_hint="用于核验程序性和审计监督依据。",
    ),
    SourceCollectionDefinition(
        collection=SourceCollection.MANAGEMENT_ECOLOGY_RESOURCES,
        label="生态环境与资源管理",
        scope="P6C 管理知识库",
        phase="P6C-management-library-buildout",
        domain="management",
        evidence_group="management",
        description="生态环境、自然资源和资源管理要求。",
        audit_hint="用于判断资源环境管理职责。",
    ),
    SourceCollectionDefinition(
        collection=SourceCollection.MANAGEMENT_URBAN_MUNICIPAL,
        label="城乡建设与市政治理",
        scope="P6C 管理知识库",
        phase="P6C-management-library-buildout",
        domain="management",
        evidence_group="management",
        description="城乡建设、市政、住房和城市治理文件。",
        audit_hint="用于核验建设和市政治理依据。",
    ),
    SourceCollectionDefinition(
        collection=SourceCollection.MANAGEMENT_GENERAL_ADMIN,
        label="综合行政管理",
        scope="P6C 管理知识库",
        phase="P6C-management-library-buildout",
        domain="management",
        evidence_group="management",
        description="综合行政、机关运行和通用管理要求。",
        audit_hint="用于补充行政管理共性依据。",
    ),
    SourceCollectionDefinition(
        collection=SourceCollection.OTHER_AGRICULTURE_WATER,
        label="农业农村与水利",
        scope="P6E 其他知识库",
        phase="P6E-other-library-buildout",
        domain="other",
        evidence_group="other",
        description="农业农村、水利和涉农管理文件。",
        audit_hint="用于涉农和水利事项的依据核验。",
    ),
    SourceCollectionDefinition(
        collection=SourceCollection.OTHER_CULTURE_TOURISM_SPORTS,
        label="文化旅游体育",
        scope="P6E 其他知识库",
        phase="P6E-other-library-buildout",
        domain="other",
        evidence_group="other",
        description="文化、旅游、体育和相关公共服务文件。",
        audit_hint="用于文旅体育事项的依据核验。",
    ),
    SourceCollectionDefinition(
        collection=SourceCollection.OTHER_DEFENSE_CONFIDENTIALITY,
        label="国防保密与征兵",
        scope="P6E 其他知识库",
        phase="P6E-other-library-buildout",
        domain="other",
        evidence_group="other",
        description="国防动员、保密和征兵相关文件。",
        audit_hint="用于敏感治理事项的依据核验。",
    ),
    SourceCollectionDefinition(
        collection=SourceCollection.OTHER_EDUCATION_RESEARCH,
        label="教育科研",
        scope="P6E 其他知识库",
        phase="P6E-other-library-buildout",
        domain="other",
        evidence_group="other",
        description="教育、科研和人才培养相关文件。",
        audit_hint="用于教育科研事项的依据核验。",
    ),
    SourceCollectionDefinition(
        collection=SourceCollection.OTHER_ETHNIC_RELIGIOUS_FOREIGN,
        label="民族宗教外事",
        scope="P6E 其他知识库",
        phase="P6E-other-library-buildout",
        domain="other",
        evidence_group="other",
        description="民族、宗教、外事和涉外管理文件。",
        audit_hint="用于民族宗教外事事项的依据核验。",
    ),
    SourceCollectionDefinition(
        collection=SourceCollection.OTHER_TRANSPORT_MARITIME,
        label="交通运输与海事",
        scope="P6E 其他知识库",
        phase="P6E-other-library-buildout",
        domain="other",
        evidence_group="other",
        description="交通运输、道路、水运和海事管理文件。",
        audit_hint="用于交通海事事项的依据核验。",
    ),
    SourceCollectionDefinition(
        collection=SourceCollection.PERSONAL_MATERIALS,
        label="个人材料",
        scope="个人上传材料",
        phase="personal-materials",
        domain="personal",
        evidence_group="personal",
        description="用户上传的院内材料、台账和复核附件。",
        audit_hint="用于补充院内证据，需先完成材料治理。",
    ),
)

SYSTEM_SOURCE_COLLECTION_DEFINITIONS: tuple[SourceCollectionDefinition, ...] = tuple(
    definition
    for definition in SOURCE_COLLECTION_DEFINITIONS
    if definition.collection != SourceCollection.PERSONAL_MATERIALS
)

_SOURCE_COLLECTION_DEFINITIONS_BY_COLLECTION = {
    definition.collection: definition for definition in SOURCE_COLLECTION_DEFINITIONS
}


def source_collection_definition(
    collection: SourceCollection,
) -> SourceCollectionDefinition:
    return _SOURCE_COLLECTION_DEFINITIONS_BY_COLLECTION[collection]
