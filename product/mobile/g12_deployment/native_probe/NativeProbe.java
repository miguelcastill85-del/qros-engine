package app.qros.g12.accessibility_probe;

import android.app.Activity;
import android.app.Instrumentation;
import android.os.Bundle;
import android.view.accessibility.AccessibilityNodeInfo;
import org.json.JSONArray;
import org.json.JSONObject;

/** Read native accessibility hints omitted by adb uiautomator's XML serializer. */
public final class NativeProbe extends Instrumentation {
  private static final String APP = "app.qros.qros_mobile_studio";

  @Override public void onCreate(Bundle arguments) { super.onCreate(arguments); start(); }

  private static String text(CharSequence value) { return value == null ? "" : value.toString(); }

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
      result.putString("qros_native_fields", fields.toString());
      finish(Activity.RESULT_OK, result);
    } catch (Exception error) {
      result.putString("qros_probe_failure", error.getClass().getSimpleName());
      finish(Activity.RESULT_CANCELED, result);
    }
  }
}
