import React from 'react';
import { StyleSheet, Text, TextInput, TouchableOpacity, View, ActivityIndicator } from 'react-native';
import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { useLogin, LoginPayload } from '../../services/api/auth';

const loginSchema = yup.object({
  email: yup.string().email('Enter a valid email').required('Email is required'),
  password: yup.string().min(8, 'Password must be at least 8 characters').required('Password is required'),
});

type LoginScreenProps = {
  onSuccess: (token: string) => void;
  onForgotPassword?: () => void;
};

export const LoginScreen: React.FC<LoginScreenProps> = ({ onSuccess, onForgotPassword }) => {
  const { control, handleSubmit, formState } = useForm<LoginPayload>({
    resolver: yupResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  });
  const loginMutation = useLogin();

  const onSubmit = handleSubmit(async (values) => {
    const response = await loginMutation.mutateAsync(values);
    onSuccess(response.token);
  });

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Welcome back</Text>
      <Controller
        control={control}
        name="email"
        render={({ field: { onChange, onBlur, value } }) => (
          <View style={styles.fieldContainer}>
            <Text style={styles.label}>Email</Text>
            <TextInput
              accessibilityLabel="email-input"
              style={styles.input}
              autoCapitalize="none"
              keyboardType="email-address"
              onBlur={onBlur}
              onChangeText={onChange}
              value={value}
            />
            {formState.errors.email && <Text style={styles.error}>{formState.errors.email.message}</Text>}
          </View>
        )}
      />
      <Controller
        control={control}
        name="password"
        render={({ field: { onChange, onBlur, value } }) => (
          <View style={styles.fieldContainer}>
            <Text style={styles.label}>Password</Text>
            <TextInput
              accessibilityLabel="password-input"
              style={styles.input}
              secureTextEntry
              onBlur={onBlur}
              onChangeText={onChange}
              value={value}
            />
            {formState.errors.password && <Text style={styles.error}>{formState.errors.password.message}</Text>}
          </View>
        )}
      />
      {loginMutation.isError && (
        <Text style={styles.error}>We could not log you in. Check your credentials and try again.</Text>
      )}
      <TouchableOpacity
        accessibilityRole="button"
        onPress={onSubmit}
        style={[styles.primaryButton, loginMutation.isLoading && styles.disabledButton]}
        disabled={loginMutation.isLoading}
      >
        {loginMutation.isLoading ? (
          <ActivityIndicator color="#ffffff" />
        ) : (
          <Text style={styles.primaryButtonLabel}>Log in</Text>
        )}
      </TouchableOpacity>
      {onForgotPassword && (
        <TouchableOpacity accessibilityRole="button" onPress={onForgotPassword}>
          <Text style={styles.linkLabel}>Forgot password?</Text>
        </TouchableOpacity>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 24,
    backgroundColor: '#ffffff',
    justifyContent: 'center',
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    marginBottom: 24,
  },
  fieldContainer: {
    marginBottom: 16,
  },
  label: {
    fontSize: 14,
    color: '#4f4f4f',
    marginBottom: 6,
  },
  input: {
    borderWidth: 1,
    borderColor: '#d0d0d0',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 16,
  },
  error: {
    color: '#d42c2c',
    marginTop: 4,
  },
  primaryButton: {
    backgroundColor: '#0066ff',
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: 8,
  },
  disabledButton: {
    opacity: 0.7,
  },
  primaryButtonLabel: {
    color: '#ffffff',
    fontSize: 18,
    fontWeight: '600',
  },
  linkLabel: {
    marginTop: 16,
    color: '#0066ff',
    fontWeight: '500',
    textAlign: 'center',
  },
});
