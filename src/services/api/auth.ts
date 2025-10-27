import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient, secureTokenStorage } from './client';
import { learnerProfileKey } from '../../state/queryClient';

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
  name: string;
}

export interface PasswordSetupPayload {
  token: string;
  password: string;
}

export interface LearnerProfilePayload {
  level: string;
  goals: string[];
}

export interface AuthResponse {
  token: string;
  refreshToken?: string;
  user: {
    id: string;
    email: string;
    name: string;
  };
}

export interface LearnerProfile {
  level: string;
  goals: string[];
  updatedAt: string;
}

export const login = async (payload: LoginPayload): Promise<AuthResponse> => {
  const { data } = await apiClient.post<AuthResponse>('/auth/login', payload);
  await secureTokenStorage.setToken(data.token);
  return data;
};

export const register = async (payload: RegisterPayload): Promise<AuthResponse> => {
  const { data } = await apiClient.post<AuthResponse>('/auth/register', payload);
  await secureTokenStorage.setToken(data.token);
  return data;
};

export const setupPassword = async (payload: PasswordSetupPayload): Promise<{ success: boolean }> => {
  const { data } = await apiClient.post<{ success: boolean }>('/auth/setup-password', payload);
  return data;
};

export const setupLearnerProfile = async (payload: LearnerProfilePayload): Promise<LearnerProfile> => {
  const { data } = await apiClient.post<LearnerProfile>('/profile', payload);
  return data;
};

export const useLogin = () => {
  return useMutation({
    mutationFn: login,
  });
};

export const useRegister = () => {
  return useMutation({
    mutationFn: register,
  });
};

export const usePasswordSetup = () => {
  return useMutation({
    mutationFn: setupPassword,
  });
};

export const useLearnerProfileSetup = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: setupLearnerProfile,
    onMutate: async (newProfile) => {
      await queryClient.cancelQueries({ queryKey: learnerProfileKey });
      const previousProfile = queryClient.getQueryData<LearnerProfile>(learnerProfileKey);
      const optimisticProfile: LearnerProfile = {
        level: newProfile.level,
        goals: newProfile.goals,
        updatedAt: new Date().toISOString(),
      };
      queryClient.setQueryData<LearnerProfile>(learnerProfileKey, optimisticProfile);
      return { previousProfile };
    },
    onError: (_error, _variables, context) => {
      if (context?.previousProfile) {
        queryClient.setQueryData(learnerProfileKey, context.previousProfile);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: learnerProfileKey });
    },
  });
};
