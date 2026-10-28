/**
 * 구글 폼 4개(1차시, 2~3차시, 4차시, 투표)를 한 번에 만드는 Apps Script.
 *
 * 사용법: script.google.com → 새 프로젝트 → 이 코드를 붙여넣기 → makeAllForms 실행(권한 허용).
 * 끝나면 [실행 로그]에 폼마다 수정 주소와 학생용 주소가 나옵니다.
 * 학생용 주소는 site/app/index.html 맨 위 CONFIG 의 FORM1_URL, FORM2_URL, FORM3_URL, VOTE_URL 에 넣으세요.
 *
 * 한계 (직접 해야 하는 일):
 *  - Apps Script 는 '파일 업로드' 문항을 만들 수 없습니다. 폼 2 에는 수정 화면에서
 *    '게임 파일(.html)' 파일 업로드 문항을 직접 추가하세요 (파일 1개, 용량 상한은 1MB 이상).
 *  - 학교 계정 정책에 따라 로그인 필수 설정이 막히거나 일부 메서드가 다를 수 있습니다.
 *  - 이 스크립트는 실제 구글 계정에서 실행해 보지 못했습니다. 안 되면 docs/FORMS.md 의 표대로 직접 만드세요.
 */
var ID_PATTERN = '^[1-3](0[1-9]|1[0-6])(0[1-9]|[1-3][0-9]|40)$';

function makeAllForms() {
  makeSubmitForm_('[1차시] 서약 + 기획 제출', '앱에서 [제출용 요약 복사]를 누르고 아래에 붙여넣으세요.', '요약 붙여넣기', false);
  makeSubmitForm_('[2~3차시] 제작 제출', '앱의 [제출용 요약 복사]를 붙여넣고, 맨 아래에 게임 파일(.html)을 올리세요.', '요약 붙여넣기', true);
  makeSubmitForm_('[4차시] 성찰 제출', '앱의 [제출용 요약 복사]를 눌러 아래에 붙여넣으세요.', '요약 붙여넣기', false);
  makeVoteForm();
}

function makeSubmitForm_(title, desc, summaryTitle, needFileNote) {
  var form = FormApp.create(title);
  form.setDescription(desc);
  form.setCollectEmail(true);
  form.setLimitOneResponsePerUser(false);  // 파일 업로드 폼은 구글이 응답 1회 제한을 걸 수 있어 수동으로 확인하세요.
  var id = FormApp.createTextValidation()
    .setHelpText('학번 5자리 (예: 20315 = 2학년 3반 15번)')
    .requireTextMatchesPattern(ID_PATTERN).build();
  form.addTextItem().setTitle('학번').setRequired(true).setValidation(id);
  form.addTextItem().setTitle('이름').setRequired(true);
  form.addParagraphTextItem().setTitle(summaryTitle).setRequired(true);
  if (needFileNote) {
    form.addSectionHeaderItem().setTitle('(여기에 파일 업로드 문항 추가)')
      .setHelpText('교사 메모: 수정 화면에서 [파일 업로드] 문항 "게임 파일(.html)"을 추가하고 이 안내 항목은 지우세요.');
  }
  Logger.log(title + '\n  수정: ' + form.getEditUrl() + '\n  학생용: ' + form.getPublishedUrl());
}

function makeVoteForm() {
  var form = FormApp.create('우리 반 작품 투표');
  form.setDescription('우리 반 작품에서만 투표해요. 갤러리에서 본 작품 번호(숫자)를 입력하세요.');
  form.setCollectEmail(true);
  form.setLimitOneResponsePerUser(true);   // 학교 계정 로그인 필요
  form.setAllowResponseEdits(false);

  var cls = form.addListItem().setTitle('우리 반').setRequired(true);
  var choices = [];
  for (var i = 1; i <= 16; i++) choices.push(cls.createChoice(i + '반'));
  cls.setChoices(choices);

  var number = FormApp.createTextValidation()
    .setHelpText('작품 번호를 숫자로 입력하세요 (1~99)')
    .requireNumberBetween(1, 99).build();
  ['과학적으로 가장 정확한 작품', '가장 재미있는 작품', '가장 창의적인 작품', '가장 실용적인 작품'].forEach(function (t) {
    form.addTextItem().setTitle(t + ' (작품 번호)').setRequired(true).setValidation(number);
  });

  var ss = SpreadsheetApp.create('투표 응답');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());
  Logger.log('투표 폼\n  수정: ' + form.getEditUrl() + '\n  학생용: ' + form.getPublishedUrl() + '\n  응답 시트(공개 금지): ' + ss.getUrl());
}
