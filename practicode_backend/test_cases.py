
def load_for(task_id: str):
    # load a test suite file, NOTE: TEMP KOSTYL, WILL BE REPLACED WITH A DATABASE
    print(f'looking for practicode_backend/templates/tasks/{task_id}.tests.json')
    try:
        with open(f'practicode_backend/templates/tasks/{task_id}.tests.json') as f:
            test_cases_str = f.read()
    except FileNotFoundError as e:
        with open(f'practicode_backend/templates/tasks/default.tests.json') as f:
            test_cases_str = f.read()
    return test_cases_str
