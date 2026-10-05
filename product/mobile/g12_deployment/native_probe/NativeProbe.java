package app.qros.g12.accessibility_probe;

import android.app.Activity;
import android.app.Instrumentation;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.accessibility.AccessibilityNodeInfo;
import org.json.JSONArray;
import org.json.JSONObject;

/** Read native accessibility hints omitted by adb uiautomator's XML serializer. */
public final class NativeProbe extends Instrumentation {
  private static final String APP = "app.qros.qros_mobile_studio";

  @Override public void onCreate(Bundle arguments) { super.onCreate(arguments); start(); }

  private static String text(CharSequence value) { return value == null ? "" : value.toString(); }

  private AccessibilityNodeInfo field(AccessibilityNodeInfo node, String hint) {
    if (node == null) return null;
    if (APP.equals(text(node.getPackageName())) && "android.widget.EditText".equals(text(node.getClassName())) && text(node.getHintText()).contains(hint)) return node;
    for (int i = 0; i < node.getChildCount(); i++) {
      AccessibilityNodeInfo found = field(node.getChild(i), hint);
      if (found != null) return found;
    }
    return null;
  }

  private void verifyEditing(JSONObject record) throws Exception {
    String label = record.getString("hint").split("\\n")[0];
    AccessibilityNodeInfo input = field(getUiAutomation().getRootInActiveWindow(), label);
    if (input == null || !input.performAction(AccessibilityNodeInfo.ACTION_CLICK)) throw new IllegalStateException("field focus rejected");
    Thread.sleep(600);
    input = field(getUiAutomation().getRootInActiveWindow(), label);
    if (input == null) throw new IllegalStateException("focused field absent");
    record.put("set_text_action_after_focus", (input.getActions() & AccessibilityNodeInfo.ACTION_SET_TEXT) != 0);
    Bundle text = new Bundle();
    text.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, "SYNTHETIC_NATIVE_FIELD_PROBE");
    record.put("synthetic_set_text_accepted", input.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, text));
    Thread.sleep(300);
    input = field(getUiAutomation().getRootInActiveWindow(), label);
    if (input == null) throw new IllegalStateException("edited field absent");
    record.put("synthetic_value_length", text(input.getText()).length());
    text.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, "");
    record.put("clear_text_accepted", input.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, text));
    Thread.sleep(300);
    input = field(getUiAutomation().getRootInActiveWindow(), label);
    record.put("empty_after_clear", input != null && text(input.getText()).length() == 0);
    getUiAutomation().injectInputEvent(new KeyEvent(KeyEvent.ACTION_DOWN, KeyEvent.KEYCODE_BACK), true);
    getUiAutomation().injectInputEvent(new KeyEvent(KeyEvent.ACTION_UP, KeyEvent.KEYCODE_BACK), true);
    Thread.sleep(300);
  }

  private void collect(AccessibilityNodeInfo node, JSONArray fields, int depth) throws Exception {
    if (node == null) return;
    if (depth > 40 || fields.length() > 8) throw new IllegalStateException("native tree bound");
    if (APP.equals(text(node.getPackageName())) && "android.widget.EditText".equals(text(node.getClassName()))) {
      JSONObject field = new JSONObject();
      field.put("hint", text(node.getHintText()));
      field.put("content_description", text(node.getContentDescription()));
      // Never export a text value, even in this empty-field test.
      field.put("value_length", text(node.getText()).length());
      field.put("password", node.isPassword());
      field.put("editable", node.isEditable());
      field.put("set_text_action", node.getActionList().contains(AccessibilityNodeInfo.AccessibilityAction.ACTION_SET_TEXT));
      fields.put(field);
    }
    for (int i = 0; i < node.getChildCount(); i++) {
      AccessibilityNodeInfo child = node.getChild(i);
      collect(child, fields, depth + 1);
      if (child != null) child.recycle();
    }
  }

  @Override public void onStart() {
    Bundle result = new Bundle();
    try {
      JSONArray fields = null;
      for (int attempt = 0; attempt < 16; attempt++) {
        fields = new JSONArray();
        AccessibilityNodeInfo root = getUiAutomation().getRootInActiveWindow();
        collect(root, fields, 0);
        if (root != null) root.recycle();
        if (fields.length() == 2) break;
        Thread.sleep(500);
      }
      if (fields == null || fields.length() != 2) throw new IllegalStateException("exact QROS fields not observed");
      for (int i = 0; i < fields.length(); i++) verifyEditing(fields.getJSONObject(i));
      result.putString("qros_native_fields", fields.toString());
      finish(Activity.RESULT_OK, result);
    } catch (Exception error) {
      result.putString("qros_probe_failure", error.getClass().getSimpleName());
      finish(Activity.RESULT_CANCELED, result);
    }
  }
}
