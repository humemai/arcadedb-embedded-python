/*
 * Python-bindings bridge: Python callbacks on record events.
 *
 * RecordEvents has eight register/unregister overloads, one listener interface per event. One adapter class implements
 * the six write events (before and after create, update and delete) and forwards each to one {@link Callback}, so
 * Python implements ONE interface instead of six, and the veto of a before event is the boolean the callback returns.
 * A failure of the callback is wrapped in a DatabaseOperationException that names the event: the engine does not catch
 * it, so it reaches the statement or save() that fired the event and the transaction does not commit.
 *
 * Compiled into arcadedb-python-bridge.jar during the wheel build (scripts/Dockerfile.build and
 * scripts/build-native.sh) and consumed by Database.on() in the Python bindings.
 */
package com.arcadedb.python;

import com.arcadedb.database.Record;
import com.arcadedb.database.RecordEvents;
import com.arcadedb.event.AfterRecordCreateListener;
import com.arcadedb.event.AfterRecordDeleteListener;
import com.arcadedb.event.AfterRecordUpdateListener;
import com.arcadedb.event.BeforeRecordCreateListener;
import com.arcadedb.event.BeforeRecordDeleteListener;
import com.arcadedb.event.BeforeRecordUpdateListener;
import com.arcadedb.exception.DatabaseOperationException;

public final class PythonRecordEvents {

  /** The Python side of a listener: false from a before event vetoes the change, the result of an after event is ignored. */
  public interface Callback {
    boolean call(Record record) throws Exception;
  }

  private static final class Listener
      implements BeforeRecordCreateListener, BeforeRecordUpdateListener, BeforeRecordDeleteListener, AfterRecordCreateListener,
      AfterRecordUpdateListener, AfterRecordDeleteListener {
    private final String   event;
    private final Callback callback;

    Listener(final String event, final Callback callback) {
      this.event = event;
      this.callback = callback;
    }

    private boolean dispatch(final Record record) {
      try {
        return callback.call(record);
      } catch (final Throwable t) {
        throw new DatabaseOperationException("Python '" + event + "' callback failed: " + PythonFunctions.describe(t), t);
      }
    }

    @Override
    public boolean onBeforeCreate(final Record record) {
      return dispatch(record);
    }

    @Override
    public boolean onBeforeUpdate(final Record record) {
      return dispatch(record);
    }

    @Override
    public boolean onBeforeDelete(final Record record) {
      return dispatch(record);
    }

    @Override
    public void onAfterCreate(final Record record) {
      dispatch(record);
    }

    @Override
    public void onAfterUpdate(final Record record) {
      dispatch(record);
    }

    @Override
    public void onAfterDelete(final Record record) {
      dispatch(record);
    }
  }

  private PythonRecordEvents() {
  }

  /**
   * Registers {@code callback} for {@code event} (before_create, after_create, before_update, after_update,
   * before_delete or after_delete) on {@code events}, the registry of a database or of one type. Returns the handle that
   * {@link #unregister} takes.
   */
  public static Object register(final RecordEvents events, final String event, final Callback callback) {
    final Listener listener = new Listener(event, callback);
    switch (event) {
    case "before_create" -> events.registerListener((BeforeRecordCreateListener) listener);
    case "before_update" -> events.registerListener((BeforeRecordUpdateListener) listener);
    case "before_delete" -> events.registerListener((BeforeRecordDeleteListener) listener);
    case "after_create" -> events.registerListener((AfterRecordCreateListener) listener);
    case "after_update" -> events.registerListener((AfterRecordUpdateListener) listener);
    case "after_delete" -> events.registerListener((AfterRecordDeleteListener) listener);
    default -> throw new IllegalArgumentException("Unknown record event: " + event);
    }
    return listener;
  }

  /** Removes the listener {@code handle} from {@code events}. */
  public static void unregister(final RecordEvents events, final String event, final Object handle) {
    final Listener listener = (Listener) handle;
    switch (event) {
    case "before_create" -> events.unregisterListener((BeforeRecordCreateListener) listener);
    case "before_update" -> events.unregisterListener((BeforeRecordUpdateListener) listener);
    case "before_delete" -> events.unregisterListener((BeforeRecordDeleteListener) listener);
    case "after_create" -> events.unregisterListener((AfterRecordCreateListener) listener);
    case "after_update" -> events.unregisterListener((AfterRecordUpdateListener) listener);
    case "after_delete" -> events.unregisterListener((AfterRecordDeleteListener) listener);
    default -> throw new IllegalArgumentException("Unknown record event: " + event);
    }
  }
}
