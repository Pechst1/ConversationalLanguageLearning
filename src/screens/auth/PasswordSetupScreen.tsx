import React from 'react';
import { ActivityIndicator, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { usePasswordSetup } from '../../services/api/auth';

interface PasswordSetupForm {
  token: string;
  password: string;
  confirmPassword: string;
}

const passwordSetupSchema = yup
  .object({
    token: yup.string().required('Invite token is required'),
    password: yup.string().min(8, 'Password must be at least 8 characters').required('Password is required'),
    confirmPassword: yup
      .string()
      .oneOf([yup.ref('password')], 'Passwords must match')
      .required('Please confirm your password'),
  })
  .required();

type PasswordSetupScreenProps = {
  onSuccess: () => void;
};

export const PasswordSetupScreen: React.FC<PasswordSetupScreenProps> = ({ onSuccess }) => {
  const { control, handleSubmit, formState } = useForm<PasswordSetupForm>({
    resolver: yupResolver(passwordSetupSchema),
    defaultValues: { token: '', password: '', confirmPassword: '' },
  });
  const passwordSetupMutation = usePasswordSetup();

  const onSubmit = handleSubmit(async ({ confirmPassword, ...values }) => {
    await passwordSetupMutation.mutateAsync(values);
    onSuccess();
  });

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Set up your password</Text>
      {(['token', 'password', 'confirmPassword'] as const).map((field) => (
        <Controller
          key={field}
          control={control}
          name={field}
          render={({ field: { onChange, onBlur, value } }) => (
            <View style={styles.fieldContainer}>
              <Text style={styles.label}>{labelMap[field]}</Text>
              <TextInput
                accessibilityLabel={`${field}-input`}
                style={styles.input}
                secureTextEntry={field.includes('password')}
                onBlur={onBlur}
                onChangeText={onChange}
                value={value}
                autoCapitalize={field === 'token' ? 'none' : 'none'}
              />
              {formState.errors[field] && <Text style={styles.error}>{formState.errors[field]?.message}</Text>}
            </View>
          )}
        />
      ))}
      {passwordSetupMutation.isError && (
        <Text style={styles.error}>We could not set your password. Check the token and try again.</Text>
      )}
      <TouchableOpacity
        accessibilityRole="button"
        onPress={onSubmit}
        style={[styles.primaryButton, passwordSetupMutation.isLoading && styles.disabledButton]}
        disabled={passwordSetupMutation.isLoading}
      >
        {passwordSetupMutation.isLoading ? (
          <ActivityIndicator color="#ffffff" />
        ) : (
          <Text style={styles.primaryButtonLabel}>Save password</Text>
        )}
      </TouchableOpacity>
    </View>
  );
};

const labelMap: Record<keyof PasswordSetupForm, string> = {
  token: 'Invite token',
  password: 'Password',
  confirmPassword: 'Confirm password',
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
});
