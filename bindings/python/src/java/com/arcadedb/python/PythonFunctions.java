/*
 * Python-bindings bridge: Python functions callable from SQL and openCypher.
 *
 * The engine resolves a function name through the process-wide DefaultSQLFunctionFactory, for SQL and for openCypher
 * alike (a name the Cypher executor does not know itself falls through to it). {@code Database.register_function()}
 * wraps the Python callable in a {@link Callback} (a JPype proxy) and registers it here as a plain SQLFunction. The
 * adapter owns what Python should not have to: the arity check, the wrapping of any failure of the callable into one
 * CommandExecutionException that names the function, and a revoked flag, so a plan that still holds the function
 * after unregister() fails with a clear error instead of calling into a callable the caller has given up.
 *
 * Compiled into arcadedb-python-bridge.jar during the wheel build (scripts/Dockerfile.build and
 * scripts/build-native.sh) and consumed by Database.register_function() in the Python bindings.
 */
package com.arcadedb.python;

import com.arcadedb.database.Identifiable;
import com.arcadedb.exception.CommandExecutionException;
import com.arcadedb.function.CypherBuiltinFunctions;
import com.arcadedb.function.CypherFunctionRegistry;
import com.arcadedb.function.FunctionRegistry;
import com.arcadedb.function.sql.DefaultSQLFunctionFactory;
import com.arcadedb.function.sql.SQLFunctionAbstract;
import com.arcadedb.query.sql.executor.CommandContext;

import java.util.Locale;

public final class PythonFunctions {

  /** The Python side of a function: the arguments as the engine passes them, the result as the engine takes it. */
  public interface Callback {
    Object call(Object[] args) throws Exception;
  }

  private static final class PythonSQLFunction extends SQLFunctionAbstract {
    private final Callback callback;
    private final int      minArgs;
    private final int      maxArgs;
    private final boolean  deterministic;
    private volatile boolean revoked;

    PythonSQLFunction(final String name, final Callback callback, final int minArgs, final int maxArgs,
        final boolean deterministic) {
      super(name);
      this.callback = callback;
      this.minArgs = minArgs;
      this.maxArgs = maxArgs;
      this.deterministic = deterministic;
    }

    @Override
    public int getMinArgs() {
      return minArgs;
    }

    @Override
    public int getMaxArgs() {
      return maxArgs;
    }

    @Override
    public boolean isDeterministic() {
      return deterministic;
    }

    @Override
    public String getSyntax() {
      return name + "(" + (maxArgs == 0 ? "" : "<args>") + ") [Python]";
    }

    @Override
    public Object execute(final Object self, final Identifiable currentRecord, final Object currentResult,
        final Object[] params, final CommandContext context) {
      if (revoked)
        throw new CommandExecutionException("Python function '" + name + "' was unregistered");
      if (params.length < minArgs || params.length > maxArgs)
        throw new CommandExecutionException("Python function '" + name + "' takes " + arity() + " argument(s), got " + params.length);
      try {
        return callback.call(params);
      } catch (final Throwable t) {
        throw new CommandExecutionException("Python function '" + name + "' failed: " + describe(t), t);
      }
    }

    private String arity() {
      if (minArgs == maxArgs)
        return String.valueOf(minArgs);
      return maxArgs == Integer.MAX_VALUE ? "at least " + minArgs : minArgs + " to " + maxArgs;
    }
  }

  private PythonFunctions() {
  }

  static String describe(final Throwable t) {
    final String message = t.getMessage();
    return message == null || message.isEmpty() ? t.getClass().getName() : message;
  }

  private static String key(final String name) {
    return name.toLowerCase(Locale.ENGLISH);
  }

  /**
   * Whether {@code name} already resolves to something that is not a Python function: a built-in SQL function, a
   * Cypher function, or one an application registered from Java. Such a name is never replaced.
   */
  public static synchronized boolean isTakenByEngine(final String name) {
    final String key = key(name);
    final DefaultSQLFunctionFactory factory = DefaultSQLFunctionFactory.getInstance();
    if (factory.hasFunction(key))
      return !(factory.getFunctionInstance(key) instanceof PythonSQLFunction);
    return CypherBuiltinFunctions.isBuiltin(key) || CypherFunctionRegistry.hasFunction(key) || FunctionRegistry.hasFunction(key);
  }

  /** Whether {@code name} is currently a Python function. */
  public static synchronized boolean isPythonFunction(final String name) {
    final String key = key(name);
    final DefaultSQLFunctionFactory factory = DefaultSQLFunctionFactory.getInstance();
    return factory.hasFunction(key) && factory.getFunctionInstance(key) instanceof PythonSQLFunction;
  }

  /** Registers (or replaces a Python function of the same name) for SQL and openCypher. Returns the handle. */
  public static synchronized Object register(final String name, final Callback callback, final int minArgs,
      final int maxArgs, final boolean deterministic) {
    if (isTakenByEngine(name))
      throw new IllegalArgumentException("'" + name + "' is already a function of the engine");
    unregister(name);
    final PythonSQLFunction function = new PythonSQLFunction(key(name), callback, minArgs, maxArgs, deterministic);
    DefaultSQLFunctionFactory.getInstance().register(function);
    return function;
  }

  /**
   * Removes the function {@code handle} (as returned by {@link #register}) if it is still the one registered under its
   * name, and revokes it. Returns whether it was registered.
   */
  public static synchronized boolean unregisterHandle(final Object handle) {
    if (!(handle instanceof PythonSQLFunction function))
      return false;
    return remove(function.getName(), function);
  }

  /** Removes whatever Python function is registered under {@code name}. Returns whether there was one. */
  public static synchronized boolean unregister(final String name) {
    final String key = key(name);
    final DefaultSQLFunctionFactory factory = DefaultSQLFunctionFactory.getInstance();
    if (!factory.hasFunction(key))
      return false;
    return factory.getFunctionInstance(key) instanceof PythonSQLFunction function && remove(key, function);
  }

  private static boolean remove(final String key, final PythonSQLFunction function) {
    function.revoked = true;
    final DefaultSQLFunctionFactory factory = DefaultSQLFunctionFactory.getInstance();
    if (!factory.hasFunction(key) || factory.getFunctionInstance(key) != function)
      return false;
    factory.unregister(key);
    FunctionRegistry.unregister(key);
    return true;
  }
}
