import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { AppNavigator } from './AppNavigator';
import { AuthNavigator } from './AuthNavigator';
import type { AuthTokens } from '../types/api';

export interface RootNavigatorProps {
  isAuthenticated: boolean;
  onAuthenticated: (tokens: AuthTokens) => void;
  onSignOut: () => void;
}

export const RootNavigator: React.FC<RootNavigatorProps> = ({
  isAuthenticated,
  onAuthenticated,
  onSignOut,
}) => {
  return (
    <NavigationContainer>
      {isAuthenticated ? (
        <AppNavigator onSignOut={onSignOut} />
      ) : (
        <AuthNavigator onAuthenticated={onAuthenticated} />
      )}
    </NavigationContainer>
  );
};
