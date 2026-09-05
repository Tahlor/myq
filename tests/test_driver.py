from myq_bridge.driver import MyQDriver


def test_normalize_state_handles_common_labels():
    assert MyQDriver.normalize_state("OPEN") == "open"
    assert MyQDriver.normalize_state("Garage Closed") == "closed"
    assert MyQDriver.normalize_state("Opening door") == "opening"
    assert MyQDriver.normalize_state(None) == "unknown"


def test_visible_nodes_and_state_tokens():
    xml = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
    <hierarchy rotation="0">
      <node text="Garage Door" resource-id="com.myq:id/name" class="android.widget.TextView" clickable="false" bounds="[0,0][100,30]" />
      <node text="Closed" resource-id="com.myq:id/state" class="android.widget.TextView" clickable="false" bounds="[0,30][100,60]" />
      <node text="" content-desc="Open garage" resource-id="com.myq:id/action" class="android.widget.Button" clickable="true" bounds="[0,60][100,100]" />
    </hierarchy>"""
    nodes = MyQDriver.visible_nodes(xml)
    assert [node["resource_id"] for node in nodes] == [
        "com.myq:id/name",
        "com.myq:id/state",
        "com.myq:id/action",
    ]
    assert MyQDriver.infer_state_tokens(xml) == ["closed"]
