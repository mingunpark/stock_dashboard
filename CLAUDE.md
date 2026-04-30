# 주식 분석 사이트

## 프로젝트 개요
사용자가 보유한 주식 종목 매수/매도 의견 제시 및 자본금 상황에 따라 신규 종목 추천 사이트
세계 경제/정세 뉴스, 기술지표, 업황 분석 등 전반적인 주식 관련 분석 기법을 사용하여 종목 분석.

## 사용자
개인 투자자 (본인)

## 아직 미결정 사항
- 기술 스택
- 데이터 소스
- 배포 방식

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health