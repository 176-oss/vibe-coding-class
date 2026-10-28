/**
 * 반별 투표 구글 폼을 자동으로 만드는 Apps Script (선택 사항).
 *
 * 사용법: script.google.com → 새 프로젝트 → 이 코드를 붙여넣기 → makeVoteForm 실행(권한 허용).
 * 실행이 끝나면 [실행 로그]에 폼 수정 주소, 학생용 주소, 응답 시트 주소가 나옵니다.
 *
 * 주의: 이 스크립트는 실제 구글 계정에서 실행해 보지 못했습니다. 학교 계정 정책에 따라 막히거나
 * 일부 메서드가 다를 수 있으니, 안 되면 docs/FORMS.md 의 표대로 폼을 직접 만드세요.
 */
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
    .requireNumberBetween(1, 99)
    .build();
  ['과학적으로 가장 정확한 작품', '가장 재미있는 작품', '가장 창의적인 작품', '가장 실용적인 작품'].forEach(function (t) {
    form.addTextItem().setTitle(t + ' (작품 번호)').setRequired(true).setValidation(number);
  });

  var ss = SpreadsheetApp.create('투표 응답');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());

  Logger.log('폼 수정 주소: ' + form.getEditUrl());
  Logger.log('학생용 주소: ' + form.getPublishedUrl());
  Logger.log('응답 시트(공개 금지, 이메일 포함): ' + ss.getUrl());
}
