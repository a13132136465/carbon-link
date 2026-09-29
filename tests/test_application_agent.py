from app.application_agent import run_application_agent
from app.config import settings
from tests.test_workflow import register, login


def test_agent_collect_validate_and_confirm(client, monkeypatch):
    monkeypatch.setattr(settings, 'llm_api_key', None)
    register(client, 'agent@example.com')
    headers = login(client, 'agent@example.com')
    def ask(**body):
        response = client.post('/api/v1/application-agent/message', headers=headers, json=body)
        assert response.status_code == 200, response.text
        return response.json()
    first = ask(message='项目名称：深圳光伏一期；项目类型：可再生能源；所在地区：广东深圳')
    assert first['draft']['name'] == '深圳光伏一期'
    assert first['draft']['project_type'] == 'renewable_energy'
    assert 'methodology' in first['missing_fields']
    assert first['model_available'] is False
    second = ask(message='方法学：CM-001；预计减排量：-3；项目说明：园区屋顶光伏发电', draft=first['draft'])
    assert second['stage'] == 'collect_project'
    assert 'estimated_tonnes' in second['missing_fields']
    ready = ask(message='预计减排量：500 tCO₂e', draft=second['draft'])
    assert ready['stage'] == 'confirm_project'
    assert ready['missing_fields'] == []
    assert client.get('/api/v1/projects?mine=true', headers=headers).json() == []
    created = client.post('/api/v1/projects', headers=headers, json=ready['draft'])
    assert created.status_code == 201
    project_id = created.json()['id']
    overview = ask(project_id=project_id, message='查看项目概况')
    assert '广东深圳' in overview['reply']
    assert '500' in overview['reply']
    method = ask(project_id=project_id, message='如何准备方法学说明？')
    assert 'CM-001' in method['reply']
    assert '额外性' in method['reply']
    register(client, 'other-agent@example.com')
    other = login(client, 'other-agent@example.com')
    assert client.post('/api/v1/application-agent/message', headers=other, json={'project_id':project_id,'message':'项目概况'}).status_code == 403


def test_agent_locked_status_and_model_failure(monkeypatch):
    class BrokenModel:
        def invoke(self, *args):
            raise TimeoutError()
    monkeypatch.setattr('app.application_agent._model', lambda: BrokenModel())
    result = run_application_agent({'message':'下一步？', 'project':{'name':'已提交项目','status':'pending','review_note':None}, 'missing_documents':[]})
    assert result['stage'] == 'under_review'
    assert '等待平台审核' in result['reply']
    assert result['model_available'] is False


def test_agent_does_not_invent_missing_fields(monkeypatch):
    monkeypatch.setattr(settings, 'llm_api_key', None)
    result = run_application_agent({'message':'帮我新建一个项目'})
    assert result['draft'] == {}
    assert len(result['missing_fields']) == 6
    oversized = run_application_agent({'message':'项目名称：' + '长' * 300})
    assert 'name' in oversized['missing_fields']


def test_model_extraction_preserves_draft_and_uses_history(monkeypatch):
    import json
    from app.schemas import AgentDraft
    from app.application_agent import ProjectExtraction
    from types import SimpleNamespace
    seen = []
    class StructuredModel:
        def with_structured_output(self, schema):
            assert schema is ProjectExtraction
            self.extracting = True
            return self
        def invoke(self, messages):
            seen.append(json.loads(messages[-1][1]))
            if self.extracting:
                self.extracting = False
                return ProjectExtraction(updates=AgentDraft(region='广东深圳', estimated_tonnes='650'))
            return SimpleNamespace(content='已经把地区更新为深圳，减排量调整为650吨，请核对自动填好的表单。')
    monkeypatch.setattr('app.application_agent._model', lambda: StructuredModel())
    result = run_application_agent({
        'message':'地区改成广东深圳，预计减排量是650吨',
        'draft':{'name':'光伏一期','project_type':'renewable_energy','region':'广东广州','methodology':'CM-001','description':'屋顶光伏'},
        'history':[{'role':'user','content':'我想申报光伏一期'}],
    })
    assert result['model_available'] is True
    assert result['stage'] == 'confirm_project'
    assert result['draft']['name'] == '光伏一期'
    assert result['draft']['region'] == '广东深圳'
    assert result['draft']['estimated_tonnes'] == '650'
    assert seen[0]['history'][0]['content'] == '我想申报光伏一期'
    assert seen[1]['missing_fields'] == []
    assert result['reply'] == '已经把地区更新为深圳，减排量调整为650吨，请核对自动填好的表单。'


def test_model_answers_with_project_and_document_context(monkeypatch):
    import json
    from types import SimpleNamespace
    captured = []
    class AnswerModel:
        def invoke(self, messages):
            captured.append(json.loads(messages[-1][1]))
            return SimpleNamespace(content='已上传项目设计文件，仍需补充权属证明。')
    monkeypatch.setattr('app.application_agent._model', lambda: AnswerModel())
    result = run_application_agent({'message':'材料准备情况？','project':{'name':'光伏一期','status':'draft','review_note':None},'documents':[{'category':'project_design','name':'PDD.pdf'}],'missing_documents':['ownership']})
    assert result['model_available'] is True
    assert result['reply'] == '已上传项目设计文件，仍需补充权属证明。'
    assert captured[0]['documents'][0]['name'] == 'PDD.pdf'
    assert captured[0]['project']['name'] == '光伏一期'


def test_followup_receives_validated_gaps_and_can_clear_wrong_values(monkeypatch):
    import json
    from types import SimpleNamespace
    from app.application_agent import ProjectExtraction
    from app.schemas import AgentDraft
    calls = []
    class GuidedModel:
        def with_structured_output(self, schema):
            self.extracting = True
            return self
        def invoke(self, messages):
            calls.append(json.loads(messages[-1][1]))
            if self.extracting:
                self.extracting = False
                return ProjectExtraction(updates=AgentDraft(description='工厂屋顶光伏，为园区供电'), clear_fields=['estimated_tonnes'])
            return SimpleNamespace(content='已整理好屋顶光伏的项目说明，也清除了不确定的减排量。你预计每年能发多少电？有发电量数据后，我们再梳理减排量的计算依据。')
    monkeypatch.setattr('app.application_agent._model', lambda: GuidedModel())
    result = run_application_agent({'message':'刚才的12000吨不确定，先删掉。主要是在厂房屋顶发电，给园区供电。','draft':{'name':'测试项目','project_type':'renewable_energy','region':'深圳','estimated_tonnes':'12000'}})
    assert 'estimated_tonnes' not in result['draft']
    assert result['draft']['description'] == '工厂屋顶光伏，为园区供电'
    assert set(calls[1]['missing_fields']) == {'方法学','预计减排量'}
    assert result['stage'] == 'collect_project'
    assert '每年能发多少电' in result['reply']
    assert result['model_available'] is True


def test_invalid_extracted_amount_is_passed_to_model_for_clarification(monkeypatch):
    import json
    from types import SimpleNamespace
    from app.application_agent import ProjectExtraction
    from app.schemas import AgentDraft
    class InvalidAmountModel:
        def with_structured_output(self, schema):
            self.extracting = True
            return self
        def invoke(self, messages):
            if self.extracting:
                self.extracting = False
                return ProjectExtraction(updates=AgentDraft(estimated_tonnes='-5'))
            payload = json.loads(messages[-1][1])
            assert 'estimated_tonnes' in payload['validation_issues']
            assert '预计减排量' in payload['missing_fields']
            return SimpleNamespace(content='预计减排量需要大于零，你想表达的是5吨吗？')
    monkeypatch.setattr('app.application_agent._model', lambda: InvalidAmountModel())
    result = run_application_agent({'message':'负5吨','draft':{'name':'测试项目','region':'深圳','project_type':'renewable_energy','methodology':'CM-001','description':'屋顶光伏'}})
    assert result['stage'] == 'collect_project'
    assert result['missing_fields'] == ['estimated_tonnes']
    assert '大于零' in result['reply']


def test_openai_compatible_transport_validates_json_without_langchain():
    from types import SimpleNamespace
    from app.application_agent import ApplicationModel, ProjectExtraction
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(content='{"updates":{"estimated_tonnes":"12000","project_type":"renewable_energy"},"clear_fields":[]}'))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    result = ApplicationModel(client, 'test-model').with_structured_output(ProjectExtraction).invoke([('system','提取字段'),('human','测试数据')])
    assert result.updates.estimated_tonnes == '12000'
    assert calls[0]['response_format'] == {'type':'json_object'}
    assert calls[0]['messages'][1]['role'] == 'user'
    assert 'JSON Schema' in calls[0]['messages'][0]['content']


def test_followup_failure_keeps_extracted_form(monkeypatch):
    from app.application_agent import ProjectExtraction
    from app.schemas import AgentDraft
    class PartiallyWorkingModel:
        def with_structured_output(self, schema):
            self.extracting = True
            return self
        def invoke(self, messages):
            if self.extracting:
                self.extracting = False
                return ProjectExtraction(updates=AgentDraft(name='测试屋顶光伏'))
            raise TimeoutError()
    monkeypatch.setattr('app.application_agent._model', lambda: PartiallyWorkingModel())
    result = run_application_agent({'message':'项目叫测试屋顶光伏'})
    assert result['draft']['name'] == '测试屋顶光伏'
    assert result['model_available'] is False
    assert '暂时不可用' in result['reply']
