import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import {
  View,
  StyleSheet,
  TextInput,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator
} from 'react-native';
import { Button, Text, colors, spacing } from '../ui';
import { ApiError, login } from '../services/api';
import { saveTokens } from '../services/authStorage';

type AuthStackParamList = {
  SignIn: undefined;
};

const Stack = createNativeStackNavigator<AuthStackParamList>();

const SignInScreen: React.FC<{ onSignIn: () => void }> = ({ onSignIn }) => {
  const [email, setEmail] = React.useState('');
  const [password, setPassword] = React.useState('');
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = React.useState(false);

  const canSubmit = email.trim().length > 0 && password.length > 0;

  const handleSubmit = React.useCallback(async () => {
    if (isSubmitting || !canSubmit) {
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const tokens = await login({ email: email.trim(), password });
      await saveTokens({
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token
      });
      onSignIn();
    } catch (error) {
      if (error instanceof ApiError) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage('Unable to sign in. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  }, [canSubmit, email, isSubmitting, onSignIn, password]);

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <View style={styles.content}>
        <Text variant="headline" emphasis="bold" style={styles.heading}>
          Welcome back
        </Text>
        <Text color="textSecondary" style={styles.copy}>
          Sign in to keep learning new phrases and track your progress.
        </Text>

        <View style={styles.fieldGroup}>
          <Text variant="subtitle" emphasis="medium" style={styles.label}>
            Email
          </Text>
          <TextInput
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            keyboardType="email-address"
            autoComplete="email"
            textContentType="username"
            placeholder="you@example.com"
            style={styles.input}
            returnKeyType="next"
            editable={!isSubmitting}
          />
        </View>

        <View style={styles.fieldGroup}>
          <Text variant="subtitle" emphasis="medium" style={styles.label}>
            Password
          </Text>
          <TextInput
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            autoCapitalize="none"
            autoComplete="password"
            textContentType="password"
            placeholder="Enter your password"
            style={styles.input}
            returnKeyType="done"
            onSubmitEditing={handleSubmit}
            editable={!isSubmitting}
          />
        </View>

        {errorMessage ? (
          <Text color="error" style={styles.errorText}>
            {errorMessage}
          </Text>
        ) : null}

        <View style={styles.buttonWrapper}>
          <Button
            label={isSubmitting ? 'Signing in...' : 'Sign in'}
            onPress={handleSubmit}
            disabled={!canSubmit || isSubmitting}
          />
        </View>

        {isSubmitting ? (
          <ActivityIndicator
            color={colors.primary}
            accessibilityLabel="Signing in"
            style={styles.loadingIndicator}
          />
        ) : null}
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
    backgroundColor: colors.background
  },
  content: {
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
    marginBottom: spacing.lg
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
    backgroundColor: '#FFFFFF',
    color: colors.text
  },
  errorText: {
    marginBottom: spacing.md
  },
  buttonWrapper: {
    marginBottom: spacing.md
  },
  loadingIndicator: {
    marginTop: spacing.sm
  }
});
