import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { AppNavigator } from './AppNavigator';
import { AuthNavigator } from './AuthNavigator';

export interface RootNavigatorProps {
  isAuthenticated: boolean;
  onSignIn: () => void;
}

export const RootNavigator: React.FC<RootNavigatorProps> = ({ isAuthenticated, onSignIn }) => {
  return (
    <NavigationContainer>
      {isAuthenticated ? <AppNavigator /> : <AuthNavigator onSignIn={onSignIn} />}
    </NavigationContainer>
  );
};
