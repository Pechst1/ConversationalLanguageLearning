import React from 'react';
import { ActivityIndicator, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { useForm, Controller } from 'react-hook-form';
import { yupResolver } from '@hookform/resolvers/yup';
import * as yup from 'yup';
import { RegisterPayload, useRegister } from '../../services/api/auth';

interface RegisterForm extends RegisterPayload {
  confirmPassword: string;
}

const registerSchema = yup
  .object({
    name: yup.string().min(2, 'Name must be at least 2 characters').required('Name is required'),
    email: yup.string().email('Enter a valid email').required('Email is required'),
    password: yup.string().min(8, 'Password must be at least 8 characters').required('Password is required'),
    confirmPassword: yup
      .string()
      .oneOf([yup.ref('password')], 'Passwords must match')
      .required('Please confirm your password'),
  })
  .required();

type RegisterScreenProps = {
  onSuccess: (token: string) => void;
  onNavigateToLogin: () => void;
};

export const RegisterScreen: React.FC<RegisterScreenProps> = ({ onSuccess, onNavigateToLogin }) => {
  const { control, handleSubmit, formState } = useForm<RegisterForm>({
    resolver: yupResolver(registerSchema),
    defaultValues: {
      name: '',
      email: '',
      password: '',
      confirmPassword: '',
    },
  });
  const registerMutation = useRegister();

  const onSubmit = handleSubmit(async ({ confirmPassword, ...values }) => {
    const response = await registerMutation.mutateAsync(values);
    onSuccess(response.token);
  });

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Create your account</Text>
      {(['name', 'email', 'password', 'confirmPassword'] as const).map((field) => (
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
                autoCapitalize={field === 'email' ? 'none' : 'words'}
                keyboardType={field === 'email' ? 'email-address' : 'default'}
              />
              {formState.errors[field] && <Text style={styles.error}>{formState.errors[field]?.message}</Text>}
            </View>
          )}
        />
      ))}
      {registerMutation.isError && (
        <Text style={styles.error}>Registration failed. Try again later.</Text>
      )}
      <TouchableOpacity
        accessibilityRole="button"
        onPress={onSubmit}
        style={[styles.primaryButton, registerMutation.isLoading && styles.disabledButton]}
        disabled={registerMutation.isLoading}
      >
        {registerMutation.isLoading ? (
          <ActivityIndicator color="#ffffff" />
        ) : (
          <Text style={styles.primaryButtonLabel}>Create account</Text>
        )}
      </TouchableOpacity>
      <TouchableOpacity accessibilityRole="button" onPress={onNavigateToLogin}>
        <Text style={styles.linkLabel}>Already have an account? Log in</Text>
      </TouchableOpacity>
    </View>
  );
};

const labelMap: Record<keyof RegisterForm, string> = {
  name: 'Full name',
  email: 'Email',
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
  linkLabel: {
    marginTop: 16,
    color: '#0066ff',
    fontWeight: '500',
    textAlign: 'center',
  },
});
