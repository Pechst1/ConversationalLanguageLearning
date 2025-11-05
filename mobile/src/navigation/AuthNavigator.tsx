import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { View, StyleSheet, TextInput, KeyboardAvoidingView, Platform, ActivityIndicator } from 'react-native';
import { Button, Text, spacing, colors } from '../ui';
import { apiClient, ApiError } from '../api/client';
import type { AuthTokens } from '../types/api';

type AuthStackParamList = {
  SignIn: undefined;
};

const Stack = createNativeStackNavigator<AuthStackParamList>();

const SignInScreen: React.FC<{ onAuthenticated: (tokens: AuthTokens) => void }> = ({ onAuthenticated }) => {
  const [email, setEmail] = React.useState('');
  const [password, setPassword] = React.useState('');
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const handleSubmit = React.useCallback(async () => {
    if (!email || !password || isSubmitting) {
      return;
    }
    setError(null);
    setIsSubmitting(true);
    try {
      const tokens = await apiClient.login({ email, password });
      onAuthenticated(tokens);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to sign in';
      setError(message);
      if (err instanceof ApiError && err.status >= 500) {
        console.error('Sign in failed with server error', err);
      }
    } finally {
      setIsSubmitting(false);
    }
  }, [email, password, isSubmitting, onAuthenticated]);

  return (
    <KeyboardAvoidingView
      behavior={Platform.select({ ios: 'padding', android: undefined })}
      style={styles.container}
    >
      <View style={styles.form}>
        <Text variant="headline" emphasis="bold" style={styles.heading}>
          Welcome back
        </Text>
        <Text color="textSecondary" style={styles.copy}>
          Sign in to keep learning new phrases and track your progress.
        </Text>
        <View style={styles.fieldGroup}>
          <Text variant="subtitle" style={styles.label}>
            Email
          </Text>
          <TextInput
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="email-address"
            style={styles.input}
            placeholder="you@example.com"
            textContentType="username"
          />
        </View>
        <View style={styles.fieldGroup}>
          <Text variant="subtitle" style={styles.label}>
            Password
          </Text>
          <TextInput
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            style={styles.input}
            placeholder="••••••••"
            textContentType="password"
          />
        </View>
        {error ? (
          <Text color="error" style={styles.errorText}>
            {error}
          </Text>
        ) : null}
        <Button
          label={isSubmitting ? 'Signing in…' : 'Sign in'}
          onPress={handleSubmit}
          disabled={isSubmitting || !email || !password}
          style={styles.submitButton}
        />
        {isSubmitting ? <ActivityIndicator color={colors.primary} style={styles.activityIndicator} /> : null}
      </View>
    </KeyboardAvoidingView>
  );
};

interface AuthNavigatorProps {
  onAuthenticated: (tokens: AuthTokens) => void;
}

export const AuthNavigator: React.FC<AuthNavigatorProps> = ({ onAuthenticated }) => {
  return (
    <Stack.Navigator screenOptions={{ headerShown: false }}>
      <Stack.Screen name="SignIn">
        {() => <SignInScreen onAuthenticated={onAuthenticated} />}
      </Stack.Screen>
    </Stack.Navigator>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    padding: spacing.xl,
    backgroundColor: colors.background,
  },
  form: {
    width: '100%',
    maxWidth: 420,
    alignSelf: 'center',
  },
  heading: {
    marginBottom: spacing.lg
  },
  copy: {
    marginBottom: spacing.xl
  },
  fieldGroup: {
    marginBottom: spacing.lg
  },
  label: {
    marginBottom: spacing.xs
  },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: 16,
    color: colors.text,
    backgroundColor: '#FFFFFF'
  },
  errorText: {
    marginTop: spacing.sm,
    marginBottom: spacing.md
  },
  submitButton: {
    marginTop: spacing.lg
  },
  activityIndicator: {
    marginTop: spacing.md
  }
});
