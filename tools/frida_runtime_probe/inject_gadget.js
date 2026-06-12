"use strict";

const gadgetPath = "/data/user/0/com.universal777.magireco/files/libmagireco_gadget.so";

Java.perform(function () {
  const Runtime = Java.use("java.lang.Runtime");
  const SlotMainActivity = Java.use(
    "com.universal777.magireco.SlotMainActivity"
  );
  try {
    const runtime = Runtime.getRuntime();
    Runtime.load0
      .overload("java.lang.Class", "java.lang.String")
      .call(runtime, SlotMainActivity.class, gadgetPath);
    send({ event: "gadget_loaded", path: gadgetPath });
  } catch (error) {
    send({
      event: "gadget_load_error",
      path: gadgetPath,
      error: String(error),
    });
  }
});
